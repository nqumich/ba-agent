"""
Skill Installer for BA-Agent Skills System.

Handles installation of external skills from GitHub, git URLs, and ZIP files.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field

from backend.skills.loader import SkillLoader, InvalidSkillError
from backend.skills.models import SkillFrontmatter, Skill, SkillSourceInfo


class SkillInstallError(Exception):
    """Raised when skill installation fails."""

    pass


class GitHubRepoInfo(BaseModel):
    """GitHub repository information."""

    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    subdirectory: Optional[str] = Field(None, description="Path within repo")
    ref: Optional[str] = Field(None, description="Branch or tag")
    sha: Optional[str] = Field(None, description="Commit SHA for pinning")


class SkillInstaller:
    """
    Install and manage external skills from various sources.

    Supports:
    - GitHub repositories (owner/repo)
    - Git URLs (any git hosting service)
    - ZIP files
    - Local directories
    """

    # GitHub URL patterns
    GITHUB_PATTERNS = [
        r"^https?://github\.com/[\w-]+/[\w-]+(?:\.git)?$",
        r"^github:([\w-]+)/([\w-]+)$",
        r"^([\w-]+)/([\w-]+)$",  # Simplified owner/repo format
    ]

    def __init__(
        self,
        install_dir: Path,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize the skill installer.

        Args:
            install_dir: Directory where skills are installed (e.g., .claude/skills/)
            cache_dir: Directory for caching git clones
        """
        self.install_dir = Path(install_dir)
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # Default cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "ba-skills"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Path to registry
        self.registry_path = Path("config/skills_registry.json")

    def install_from_github(
        self,
        repo: str,
        subdirectory: Optional[str] = None,
        ref: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Skill:
        """
        Install skill from GitHub repository.

        Args:
            repo: Repository in "owner/repo" format
            subdirectory: Optional path within repo
            ref: Branch or tag (default: "main")
            auth_token: Optional GitHub PAT for private repos

        Returns:
            Installed Skill object

        Raises:
            SkillInstallError: If installation fails
        """
        # 1. Clone repo to cache
        cache_path = self._clone_to_cache(
            f"https://github.com/{repo}.git",
            ref=ref,
            auth_token=auth_token
        )

        # 2. Locate skill directory
        skill_dir = cache_path
        if subdirectory:
            skill_dir = cache_path / subdirectory

        # 3. Validate SKILL.md exists
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            # Try to find SKILL.md in subdirectories
            found = list(skill_dir.rglob("SKILL.md"))
            if not found:
                raise SkillInstallError(
                    f"No SKILL.md found in repository {repo}"
                )
            skill_md = found[0]
            skill_dir = skill_md.parent

        # 4. Parse skill name from SKILL.md
        try:
            frontmatter = self._parse_skill_frontmatter(skill_md)
            skill_name = frontmatter.name
        except Exception as e:
            raise SkillInstallError(
                f"Failed to parse SKILL.md: {e}"
            )

        # 5. Check for conflicts
        install_path = self.install_dir / skill_name
        if install_path.exists():
            raise SkillInstallError(
                f"Skill '{skill_name}' already installed. "
                f"Uninstall first or use update() instead."
            )

        # 6. Copy to install directory
        shutil.copytree(skill_dir, install_path)

        # 7. Add to registry
        self._add_to_registry(
            skill_name,
            source_type="github",
            location=repo,
            subdirectory=subdirectory,
            ref=ref,
        )

        # 8. Load and return skill
        return self._load_skill_from_path(install_path)

    def install_from_git_url(
        self,
        url: str,
        ref: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Skill:
        """
        Install skill from any git URL.

        Args:
            url: Git clone URL
            ref: Branch or tag
            auth_token: Optional auth token

        Returns:
            Installed Skill object
        """
        # Clone to cache
        cache_path = self._clone_to_cache(url, ref=ref, auth_token=auth_token)

        # Find SKILL.md
        skill_md_files = list(cache_path.rglob("SKILL.md"))
        if not skill_md_files:
            raise SkillInstallError(
                f"No SKILL.md found in repository {url}"
            )

        skill_md = skill_md_files[0]
        skill_dir = skill_md.parent

        # Parse skill
        frontmatter = self._parse_skill_frontmatter(skill_md)
        skill_name = frontmatter.name

        # Check conflicts
        install_path = self.install_dir / skill_name
        if install_path.exists():
            raise SkillInstallError(
                f"Skill '{skill_name}' already installed"
            )

        # Copy to install directory
        shutil.copytree(skill_dir, install_path)

        # Add to registry
        self._add_to_registry(
            skill_name,
            source_type="git_url",
            location=url,
            ref=ref,
        )

        return self._load_skill_from_path(install_path)

    def install_from_zip(self, zip_path: Path) -> Skill:
        """
        Install skill from ZIP archive.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Installed Skill object
        """
        if not zip_path.exists():
            raise SkillInstallError(f"ZIP file not found: {zip_path}")

        # Extract to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)

            # Find SKILL.md
            skill_md_files = list(temp_path.rglob("SKILL.md"))
            if not skill_md_files:
                raise SkillInstallError(
                    f"No SKILL.md found in ZIP archive"
                )

            skill_md = skill_md_files[0]
            skill_dir = skill_md.parent

            # Parse skill
            frontmatter = self._parse_skill_frontmatter(skill_md)
            skill_name = frontmatter.name

            # Check conflicts
            install_path = self.install_dir / skill_name
            if install_path.exists():
                raise SkillInstallError(
                    f"Skill '{skill_name}' already installed"
                )

            # Copy to install directory
            shutil.copytree(skill_dir, install_path)

            # Add to registry
            self._add_to_registry(
                skill_name,
                source_type="zip",
                location=str(zip_path),
            )

            return self._load_skill_from_path(install_path)

    def uninstall(self, skill_name: str, remove_files: bool = True) -> None:
        """
        Uninstall a skill.

        Args:
            skill_name: Name of skill to uninstall
            remove_files: Whether to delete files (default: True)

        Raises:
            SkillInstallError: If skill is not found
        """
        install_path = self.install_dir / skill_name
        if not install_path.exists():
            raise SkillInstallError(
                f"Skill '{skill_name}' is not installed"
            )

        # Remove files
        if remove_files:
            shutil.rmtree(install_path)

        # Remove from registry
        self._remove_from_registry(skill_name)

    def update(
        self,
        skill_name: str,
        current_ref: Optional[str] = None
    ) -> Skill:
        """
        Update an installed skill from its source.

        Args:
            skill_name: Name of skill to update
            current_ref: Current branch/tag (for validation)

        Returns:
            Updated Skill object

        Raises:
            SkillInstallError: If skill not found or update fails
        """
        # Get current skill info from registry
        source_info = self._get_skill_source_info(skill_name)
        if source_info is None:
            raise SkillInstallError(
                f"Skill '{skill_name}' not found in registry"
            )

        # Uninstall (remove files but keep registry entry temporarily)
        install_path = self.install_dir / skill_name
        if install_path.exists():
            shutil.rmtree(install_path)

        # Re-install from source
        if source_info.source_type == "github":
            return self.install_from_github(
                repo=source_info.location,
                subdirectory=source_info.subdirectory,
                ref=source_info.ref,
            )
        elif source_info.source_type == "git_url":
            return self.install_from_git_url(
                url=source_info.location,
                ref=source_info.ref,
            )
        else:
            raise SkillInstallError(
                f"Cannot update skill with source_type: {source_info.source_type}"
            )

    def list_installed(self) -> List[Dict[str, Any]]:
        """
        List all installed skills.

        Returns:
            List of skill information dictionaries
        """
        installed = []

        if self.install_dir.exists():
            for skill_dir in self.install_dir.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        try:
                            frontmatter = self._parse_skill_frontmatter(skill_md)
                            installed.append({
                                "name": frontmatter.name,
                                "display_name": frontmatter.display_name,
                                "description": frontmatter.description,
                                "version": frontmatter.version,
                                "category": frontmatter.category,
                                "path": str(skill_dir),
                            })
                        except Exception:
                            # Skip invalid skills
                            continue

        return sorted(installed, key=lambda x: x["name"])

    def _clone_to_cache(
        self,
        url: str,
        ref: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> Path:
        """
        Clone repository to cache directory.

        Args:
            url: Git clone URL
            ref: Optional branch or tag
            auth_token: Optional auth token

        Returns:
            Path to cloned repository
        """
        # Create cache key from URL
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.cache_dir / cache_key

        # Clean up if exists
        if cache_path.exists():
            shutil.rmtree(cache_path)

        # Construct clone command with auth
        clone_url = url
        if auth_token and "github.com" in url:
            # Inject token into URL for authentication
            parsed = url.replace("https://", "")
            clone_url = f"https://{auth_token}@{parsed}"

        # Build git command
        cmd = ["git", "clone"]
        if ref:
            cmd.extend(["--branch", ref])
        cmd.extend(["--depth", "1", clone_url, str(cache_path)])

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        except subprocess.TimeoutExpired:
            raise SkillInstallError(
                f"Git clone timed out after 5 minutes"
            )
        except subprocess.CalledProcessError as e:
            raise SkillInstallError(
                f"Git clone failed: {e.stderr}"
            )

        return cache_path

    def _parse_skill_frontmatter(self, skill_md: Path) -> SkillFrontmatter:
        """
        Parse YAML frontmatter from SKILL.md.

        Args:
            skill_md: Path to SKILL.md file

        Returns:
            Parsed SkillFrontmatter object
        """
        content = skill_md.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        if not content.startswith("---"):
            raise InvalidSkillError(
                f"SKILL.md must start with YAML frontmatter"
            )

        parts = content.split("---", 2)
        if len(parts) < 3:
            raise InvalidSkillError(
                f"SKILL.md has invalid frontmatter format"
            )

        frontmatter_text = parts[1]

        try:
            frontmatter_dict = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise InvalidSkillError(
                f"Invalid YAML in frontmatter: {e}"
            )

        return SkillFrontmatter(**frontmatter_dict)

    def _load_skill_from_path(self, skill_dir: Path) -> Skill:
        """
        Load complete Skill object from directory.

        Args:
            skill_dir: Skill directory path

        Returns:
            Skill object
        """
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # Split frontmatter and instructions
        parts = content.split("---", 2)
        frontmatter_text = parts[1]
        instructions = parts[2].strip() if len(parts) > 2 else ""

        frontmatter_dict = yaml.safe_load(frontmatter_text)
        frontmatter = SkillFrontmatter(**frontmatter_dict)

        return Skill(
            metadata=frontmatter,
            instructions=instructions,
            base_dir=skill_dir,
        )

    def _add_to_registry(
        self,
        skill_name: str,
        source_type: str,
        location: str,
        subdirectory: Optional[str] = None,
        ref: Optional[str] = None,
        sha: Optional[str] = None,
    ) -> None:
        """Add skill to installation registry."""
        import datetime

        # Load existing registry
        registry: Dict[str, Any] = {"installed": {}, "last_update": None}
        if self.registry_path.exists():
            with open(self.registry_path, "r") as f:
                registry = json.load(f)

        # Add skill
        registry["installed"][skill_name] = {
            "source_type": source_type,
            "location": location,
            "subdirectory": subdirectory,
            "ref": ref,
            "sha": sha,
            "installed_at": datetime.datetime.now().isoformat(),
        }
        registry["last_update"] = datetime.datetime.now().isoformat()

        # Save registry
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def _remove_from_registry(self, skill_name: str) -> None:
        """Remove skill from installation registry."""
        import json

        if not self.registry_path.exists():
            return

        with open(self.registry_path, "r") as f:
            registry = json.load(f)

        if skill_name in registry["installed"]:
            del registry["installed"][skill_name]

            import datetime
            registry["last_update"] = datetime.datetime.now().isoformat()

            with open(self.registry_path, "w") as f:
                json.dump(registry, f, indent=2)

    def _get_skill_source_info(self, skill_name: str) -> Optional[SkillSourceInfo]:
        """Get source information for a skill from registry."""
        import json

        if not self.registry_path.exists():
            return None

        with open(self.registry_path, "r") as f:
            registry = json.load(f)

        if skill_name not in registry["installed"]:
            return None

        info = registry["installed"][skill_name]
        return SkillSourceInfo(**info)
