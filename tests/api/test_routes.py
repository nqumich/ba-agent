"""
测试 API 路由
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import io

from backend.api.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestHealthEndpoint:
    """测试健康检查端点"""

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestSkillsEndpoints:
    """测试 Skills 管理端点"""

    def test_list_skills(self, client):
        """测试获取 Skills 列表"""
        response = client.get("/api/v1/skills")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_skill_categories(self, client):
        """测试获取 Skill 类别"""
        response = client.get("/api/v1/skills/categories")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_skills_status(self, client):
        """测试获取 Skills 状态"""
        response = client.get("/api/v1/skills/status/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_skills" in data
        assert "builtin_skills" in data


class TestAgentEndpoints:
    """测试 Agent 交互端点"""

    def test_agent_status(self, client):
        """测试获取 Agent 状态"""
        response = client.get("/api/v1/agent/status")
        assert response.status_code == 200
        data = response.json()
        assert "agent_initialized" in data
        assert "version" in data

    def test_start_conversation(self, client):
        """测试创建对话"""
        response = client.post("/api/v1/agent/conversation/start")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "conversation_id" in data["data"]


class TestFilesEndpoints:
    """测试文件管理端点"""

    def test_list_files_empty(self, client):
        """测试列出文件（空列表）"""
        response = client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_upload_file_invalid_format(self, client):
        """测试上传不支持的文件格式"""
        # 创建一个临时文件
        content = b"test content"
        files = {"file": ("test.txt", content, "text/plain")}

        response = client.post("/api/v1/files/upload", files=files)
        # 应该返回错误（不支持 .txt）
        assert response.status_code in [400, 413]

    def test_upload_file_too_large(self, client):
        """测试上传过大文件"""
        # 创建一个超过 50MB 的模拟文件
        large_content = b"x" * (51 * 1024 * 1024)
        files = {"file": ("large.xlsx", large_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        response = client.post("/api/v1/files/upload", files=files)
        # 应该返回 413（文件过大）
        assert response.status_code == 413


class TestRootEndpoint:
    """测试根路径端点"""

    def test_root(self, client):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "BA-Agent API"
        assert "docs" in data
        assert "endpoints" in data
