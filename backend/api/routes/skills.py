"""
Skills 管理路由

处理 Skills 的查询、激活、配置等
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from backend.api.state import get_app_state
from backend.skills import SkillLoader, SkillRegistry, SkillActivator
from backend.skills.models import SkillMetadata, Skill
from backend.skills.installer import SkillInstaller
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== 请求/响应模型 =====

class SkillsListResponse(BaseModel):
    """Skills 列表响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class SkillDetailResponse(BaseModel):
    """Skill 详情响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class SkillActivateRequest(BaseModel):
    """Skill 激活请求"""
    skill_name: str = Field(..., description="Skill 名称")
    conversation_id: Optional[str] = Field(None, description="对话 ID")


class SkillActivateResponse(BaseModel):
    """Skill 激活响应"""
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class SkillInstallRequest(BaseModel):
    """Skill 安装请求"""
    source: str = Field(..., description="安装源 (GitHub URL/git/ZIP)")
    skill_name: Optional[str] = Field(None, description="指定 Skill 名称")
    branch: Optional[str] = Field("main", description="GitHub 分支")


class SkillConfigUpdateRequest(BaseModel):
    """Skill 配置更新请求"""
    config: Dict[str, Any] = Field(..., description="配置参数")


# ===== 辅助函数 =====

def _get_skill_registry() -> SkillRegistry:
    """获取 SkillRegistry 实例"""
    app_state = get_app_state()
    registry = app_state.get("skill_registry")
    if not registry:
        # 初始化 SkillRegistry
        skills_dirs = [
            Path("skills"),
            Path(".claude/skills")
        ]
        loader = SkillLoader(skills_dirs)
        registry = SkillRegistry(loader)
        app_state["skill_registry"] = registry
        logger.info("SkillRegistry 初始化完成")
    return registry


def _get_skill_activator() -> SkillActivator:
    """获取 SkillActivator 实例"""
    app_state = get_app_state()
    activator = app_state.get("skill_activator")
    if not activator:
        registry = _get_skill_registry()
        activator = SkillActivator(registry)
        app_state["skill_activator"] = activator
        logger.info("SkillActivator 初始化完成")
    return activator


def _skill_metadata_to_dict(metadata: SkillMetadata) -> Dict[str, Any]:
    """将 SkillMetadata 转换为字典"""
    return {
        "name": metadata.name,
        "display_name": metadata.display_name,
        "description": metadata.description,
        "version": metadata.version,
        "category": metadata.category,
        "is_mode": metadata.is_mode,
        # 注意：SkillMetadata 是 dataclass，只有这些字段
        # author, entrypoint, function 等在 SkillFrontmatter 中
    }


def _skill_to_dict(skill: Skill) -> Dict[str, Any]:
    """将 Skill 转换为字典"""
    result = _skill_metadata_to_dict(skill.metadata)
    # 添加完整信息（来自 SkillFrontmatter）
    result.update({
        "author": skill.metadata.author,
        "entrypoint": skill.metadata.entrypoint,
        "function": skill.metadata.function,
        "requirements": skill.metadata.requirements,
        # SkillFrontmatter 没有 config 字段，使用空字典
        "config": {},
        "tags": skill.metadata.tags,
        "examples": skill.metadata.examples,
        "source": "builtin",  # 默认为内置，后续可从路径判断
        "content": skill.instructions,
        "base_dir": str(skill.base_dir)
    })
    return result


# ===== 端点 =====

@router.get("", response_model=SkillsListResponse)
async def list_skills(
    category: Optional[str] = None,
    source: Optional[str] = None  # builtin, external, all
):
    """
    获取所有可用 Skills 列表

    - category: 按 category 过滤
    - source: 按来源过滤 (暂不支持，当前都是 builtin)
    """
    try:
        registry = _get_skill_registry()
        all_metadata = registry.get_all_metadata()

        # 过滤
        skills_list = []
        for metadata in all_metadata.values():
            if category and metadata.category != category:
                continue
            # 暂时忽略 source 过滤，后续可根据路径判断
            skills_list.append(_skill_metadata_to_dict(metadata))

        # 按 category 分组
        grouped = {}
        for skill in skills_list:
            cat = skill["category"] or "Uncategorized"
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(skill)

        return SkillsListResponse(data={
            "total": len(skills_list),
            "skills": skills_list,
            "grouped": grouped
        })

    except Exception as e:
        logger.error(f"获取 Skills 列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Skills 列表失败: {str(e)}"
        )


@router.get("/categories", response_model=SkillsListResponse)
async def get_skill_categories():
    """获取所有 Skill 类别"""
    try:
        registry = _get_skill_registry()
        all_metadata = registry.get_all_metadata()

        # 统计类别
        categories = {}
        for metadata in all_metadata.values():
            cat = metadata.category or "Uncategorized"
            if cat not in categories:
                categories[cat] = {
                    "name": cat,
                    "count": 0,
                    "skills": []
                }
            categories[cat]["count"] += 1
            categories[cat]["skills"].append(metadata.name)

        return SkillsListResponse(data={
            "categories": list(categories.values())
        })

    except Exception as e:
        logger.error(f"获取 Skill 类别失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Skill 类别失败: {str(e)}"
        )


@router.get("/preferences")
async def get_skills_preferences():
    """
    获取用户 Skills 偏好设置
    """
    try:
        import json
        from pathlib import Path

        prefs_file = Path("config/skills_preferences.json")

        if not prefs_file.exists():
            return SkillsListResponse(data={
                "enabled_skills": [],
                "total": 0
            })

        with open(prefs_file, "r", encoding="utf-8") as f:
            prefs = json.load(f)

        return SkillsListResponse(data={
            "enabled_skills": prefs.get("enabled_skills", []),
            "total": len(prefs.get("enabled_skills", []))
        })

    except Exception as e:
        logger.error(f"获取 Skills 偏好失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取失败: {str(e)}"
        )


@router.post("/preferences")
async def save_skills_preferences(request: Dict[str, Any]):
    """
    保存用户 Skills 偏好设置

    - enabled_skills: 用户选择启用的 Skills 列表
    """
    try:
        enabled_skills = request.get("enabled_skills", [])

        # 保存到文件（简单实现）
        import json
        from pathlib import Path

        prefs_file = Path("config/skills_preferences.json")
        prefs_file.parent.mkdir(parents=True, exist_ok=True)

        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump({"enabled_skills": enabled_skills}, f, indent=2, ensure_ascii=False)

        logger.info(f"保存 Skills 偏好: {len(enabled_skills)} 个已启用")

        return SkillsListResponse(data={
            "message": f"已保存 {len(enabled_skills)} 个 Skills 的设置",
            "enabled_count": len(enabled_skills)
        })

    except Exception as e:
        logger.error(f"保存 Skills 偏好失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"保存失败: {str(e)}"
        )


@router.get("/{skill_name}", response_model=SkillDetailResponse)
async def get_skill_detail(skill_name: str):
    """
    获取 Skill 详情

    返回 Skill 的完整信息，包括描述、配置、示例等
    """
    try:
        registry = _get_skill_registry()

        # 检查 Skill 是否存在
        if not registry.skill_exists(skill_name):
            raise HTTPException(
                status_code=404,
                detail=f"Skill 不存在: {skill_name}"
            )

        # 获取完整内容
        skill = registry.get_skill_full(skill_name)
        if not skill:
            raise HTTPException(
                status_code=404,
                detail=f"无法加载 Skill: {skill_name}"
            )

        return SkillDetailResponse(data=_skill_to_dict(skill))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Skill 详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Skill 详情失败: {str(e)}"
        )


@router.get("/{skill_name}/config", response_model=SkillDetailResponse)
async def get_skill_config(skill_name: str):
    """
    获取 Skill 配置

    返回 Skill 的当前配置参数
    """
    try:
        registry = _get_skill_registry()
        metadata = registry.get_skill_metadata(skill_name)

        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Skill 不存在: {skill_name}"
            )

        return SkillDetailResponse(data={
            "skill_name": skill_name,
            "config": metadata.config
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Skill 配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Skill 配置失败: {str(e)}"
        )


@router.put("/{skill_name}/config", response_model=SkillDetailResponse)
async def update_skill_config(
    skill_name: str,
    request: SkillConfigUpdateRequest
):
    """
    更新 Skill 配置

    更新 Skill 的运行时配置参数
    """
    try:
        # TODO: 实现配置更新逻辑
        # 需要更新 config/skills.yaml 或运行时配置

        return SkillDetailResponse(data={
            "skill_name": skill_name,
            "config": request.config,
            "message": "配置更新功能待实现"
        })

    except Exception as e:
        logger.error(f"更新 Skill 配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"更新 Skill 配置失败: {str(e)}"
        )


@router.post("/activate", response_model=SkillActivateResponse)
async def activate_skill(request: SkillActivateRequest):
    """
    激活 Skill

    将 Skill 激活并注入到对话上下文中
    """
    try:
        activator = _get_skill_activator()

        # 激活 Skill
        result = activator.activate_skill(
            request.skill_name,
            conversation_id=request.conversation_id
        )

        return SkillActivateResponse(data={
            "skill_name": request.skill_name,
            "activated": result.success,
            "messages": result.messages,
            "context_modifier": result.context_modifier.model_dump() if result.context_modifier else None
        })

    except Exception as e:
        logger.error(f"激活 Skill 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"激活 Skill 失败: {str(e)}"
        )


@router.post("/install", response_model=SkillDetailResponse)
async def install_skill(request: SkillInstallRequest):
    """
    安装外部 Skill

    从 GitHub/git/ZIP 安装外部 Skill
    """
    try:
        # 初始化 SkillInstaller
        installer = SkillInstaller(
            install_dir=Path("skills"),
            registry_file=Path("config/skills_registry.json")
        )

        # 安装 Skill
        skill_path = installer.install(
            source=request.source,
            skill_name=request.skill_name,
            branch=request.branch
        )

        # 重新加载 SkillRegistry
        app_state = get_app_state()
        app_state["skill_registry"] = None  # 清除缓存

        return SkillDetailResponse(data={
            "message": "Skill 安装成功",
            "skill_path": str(skill_path)
        })

    except Exception as e:
        logger.error(f"安装 Skill 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"安装 Skill 失败: {str(e)}"
        )


@router.delete("/{skill_name}")
async def uninstall_skill(skill_name: str):
    """
    卸载 Skill

    卸载外部安装的 Skill（内置 Skill 不能卸载）
    """
    try:
        registry = _get_skill_registry()
        metadata = registry.get_skill_metadata(skill_name)

        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Skill 不存在: {skill_name}"
            )

        # 检查是否为内置 Skill
        if metadata.source == "builtin":
            raise HTTPException(
                status_code=400,
                detail=f"内置 Skill 不能卸载: {skill_name}"
            )

        # TODO: 实现卸载逻辑
        # 需要从 skills/ 目录删除 Skill 文件
        # 并更新 skills_registry.json

        return {
            "success": True,
            "message": "Skill 卸载功能待实现",
            "skill_name": skill_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"卸载 Skill 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"卸载 Skill 失败: {str(e)}"
        )


@router.get("/status/overview")
async def get_skills_status():
    """
    获取 Skills 系统状态概览

    返回 Skills 系统的统计信息
    """
    try:
        registry = _get_skill_registry()
        all_metadata = registry.get_all_metadata()

        # 统计（暂时全部算作内置，后续可根据路径判断）
        builtin_count = len(all_metadata)
        external_count = 0

        # 按类别统计
        category_stats = {}
        for metadata in all_metadata.values():
            cat = metadata.category or "Uncategorized"
            category_stats[cat] = category_stats.get(cat, 0) + 1

        return {
            "total_skills": len(all_metadata),
            "builtin_skills": builtin_count,
            "external_skills": external_count,
            "categories": len(category_stats),
            "category_stats": category_stats
        }

    except Exception as e:
        logger.error(f"获取 Skills 状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取 Skills 状态失败: {str(e)}"
        )


__all__ = ["router"]
