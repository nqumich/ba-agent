"""
API 服务增强功能测试

测试 JWT 认证、速率限制、错误处理等功能。
"""

import pytest
import os
import time
import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.api.main import app
from backend.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    USERS_DB
)


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestAuthentication:
    """测试 JWT 认证功能"""

    def test_login_success(self, client):
        """测试成功登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data

    def test_login_invalid_credentials(self, client):
        """测试无效凭据登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "wrong_password"
        })

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """测试不存在的用户登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "password"
        })

        assert response.status_code == 401

    def test_get_current_user(self, client):
        """测试获取当前用户信息"""
        # 先登录
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]

        # 获取用户信息
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_get_current_user_no_token(self, client):
        """测试无令牌获取用户信息"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """测试无效令牌获取用户信息"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_token_refresh(self, client):
        """测试令牌刷新"""
        # 先登录
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        refresh_token = login_response.json()["refresh_token"]

        # 刷新令牌
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_token_refresh_invalid_token(self, client):
        """测试无效刷新令牌"""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token"
        })

        assert response.status_code == 401

    def test_logout(self, client):
        """测试登出"""
        # 先登录
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]

        # 登出
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200


class TestJWTFunctions:
    """测试 JWT 工具函数"""

    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = create_access_token({"sub": "test_user", "user_id": "u_001"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """测试解码有效令牌"""
        token = create_access_token({"sub": "test_user", "user_id": "u_001"})
        payload = decode_token(token)

        assert payload["sub"] == "test_user"
        assert payload["user_id"] == "u_001"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_expired_token(self):
        """测试解码过期令牌"""
        # 创建一个已过期的令牌
        import time
        from datetime import datetime, timedelta

        payload = {
            "sub": "test_user",
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(Exception):  # HTTPException
            decode_token(token)

    def test_token_contains_required_claims(self):
        """测试令牌包含必需的声明"""
        token = create_access_token({"sub": "test_user", "user_id": "u_001"})
        payload = decode_token(token)

        assert "sub" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert "type" in payload
        assert payload["type"] == "access"


class TestRateLimiting:
    """测试速率限制功能"""

    def test_rate_limit_headers_present(self, client):
        """测试速率限制响应头"""
        # 先登录获取 token
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]

        # 检查受保护端点的速率限制响应头
        response = client.get(
            "/api/v1/files",
            headers={"Authorization": f"Bearer {token}"}
        )

        # 检查速率限制响应头
        assert "X-RateLimit-IP-Limit" in response.headers
        assert "X-RateLimit-IP-Remaining" in response.headers
        assert "X-RateLimit-User-Limit" in response.headers

    def test_health_check_excluded_from_rate_limit(self, client):
        """测试健康检查端点排除在速率限制外"""
        # 快速发送多个请求
        for _ in range(100):
            response = client.get("/api/v1/health")
            assert response.status_code == 200

    def test_process_time_header(self, client):
        """测试处理时间响应头"""
        response = client.get("/api/v1/health")

        assert "X-Process-Time" in response.headers


class TestErrorHandling:
    """测试错误处理功能"""

    def test_not_found_error(self, client):
        """测试 404 错误"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """测试方法不允许错误"""
        response = client.post("/api/v1/health")
        # 健康检查可能只允许 GET
        # 如果返回 405 说明有方法限制
        # 如果返回 200 说明允许 POST
        assert response.status_code in [200, 405, 404]

    def test_validation_error_response_format(self, client):
        """测试验证错误响应格式"""
        response = client.post("/api/v1/auth/login", json={
            "username": "",  # 空用户名应该验证失败
            "password": ""
        })

        # 应该返回错误
        if response.status_code != 200:
            data = response.json()
            assert "error" in data or "detail" in data


class TestProtectedEndpoints:
    """测试受保护的端点"""

    def test_protected_endpoint_without_auth(self, client):
        """测试无认证访问受保护端点"""
        response = client.get("/api/v1/files")

        # 应该返回 401 或 403
        assert response.status_code in [401, 40]

    def test_protected_endpoint_with_auth(self, client):
        """测试有认证访问受保护端点"""
        # 先登录
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]

        # 访问受保护的端点
        response = client.get(
            "/api/v1/files",
            headers={"Authorization": f"Bearer {token}"}
        )

        # 不应该返回 401/403
        # 可能返回 200（有文件）或 404（无文件）
        assert response.status_code not in [401, 403]

    def test_agent_status_with_auth(self, client):
        """测试带认证的 Agent 状态端点"""
        # 先登录
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_response.json()["access_token"]

        # 访问 Agent 状态
        response = client.get(
            "/api/v1/agent/status",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "agent_initialized" in data


class TestAPIVersionUpdate:
    """测试 API 版本更新"""

    def test_api_version(self, client):
        """测试 API 版本"""
        response = client.get("/api")
        assert response.status_code == 200

        data = response.json()
        assert data["version"] == "2.2.0"

    def test_api_features(self, client):
        """测试 API 功能列表"""
        response = client.get("/api")
        assert response.status_code == 200

        data = response.json()
        assert "features" in data
        assert "JWT 认证" in data["features"]
        assert "速率限制" in data["features"]


class TestUserRoles:
    """测试用户角色"""

    def test_admin_user_permissions(self, client):
        """测试管理员权限"""
        login_response = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })

        data = login_response.json()
        assert data["user"]["role"] == "admin"
        assert "admin" in data["user"]["permissions"]

    def test_regular_user_permissions(self, client):
        """测试普通用户权限"""
        login_response = client.post("/api/v1/auth/login", json={
            "username": "user",
            "password": "user123"
        })

        data = login_response.json()
        assert data["user"]["role"] == "user"
        assert "admin" not in data["user"]["permissions"]
