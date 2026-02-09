"""
JWT 认证和授权模块

提供基于 JWT 的用户认证和权限管理功能。
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# JWT 配置
JWT_SECRET_KEY = os.environ.get("BA_JWT_SECRET_KEY", "ba-agent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("BA_JWT_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("BA_JWT_REFRESH_DAYS", "7"))

# 密码加密 - 使用 sha256_crypt 避免 bcrypt 的 72 字节限制
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# HTTP Bearer 安全方案
security = HTTPBearer(auto_error=False)


# ===== 用户模型 =====

class User:
    """用户模型"""

    def __init__(
        self,
        username: str,
        user_id: str,
        email: Optional[str] = None,
        role: str = "user",
        permissions: List[str] = None
    ):
        self.username = username
        self.user_id = user_id
        self.email = email
        self.role = role
        self.permissions = permissions or []


# ===== 模拟用户存储 =====

# 生产环境应该使用数据库
# 注意：密码哈希在首次使用时计算，避免模块加载时的 bcrypt 问题
_USERS_DB_RAW: Dict[str, Dict[str, Any]] = {
    # 默认管理员账户 (生产环境必须修改密码)
    "admin": {
        "user_id": "u_001",
        "username": "admin",
        "email": "admin@ba-agent.local",
        "password": "admin123",  # 原始密码
        "hashed_password": None,  # 延迟计算
        "role": "admin",
        "permissions": ["read", "write", "delete", "admin"]
    },
    # 默认用户账户
    "user": {
        "user_id": "u_002",
        "username": "user",
        "email": "user@ba-agent.local",
        "password": "user123",  # 原始密码
        "hashed_password": None,  # 延迟计算
        "role": "user",
        "permissions": ["read", "write"]
    }
}

# 运行时用户数据库（包含哈希后的密码）
USERS_DB: Dict[str, Dict[str, Any]] = {}


def _ensure_password_hashed():
    """确保密码已被哈希"""
    for username, user_data in _USERS_DB_RAW.items():
        if user_data["hashed_password"] is None:
            user_data["hashed_password"] = pwd_context.hash(user_data["password"])
        USERS_DB[username] = user_data


# 首次使用时初始化
_ensure_password_hashed()


# ===== JWT 工具函数 =====

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        JWT 令牌字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    创建刷新令牌

    Args:
        data: 要编码的数据

    Returns:
        JWT 刷新令牌字符串
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    解码并验证 JWT 令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        解码后的数据

    Raises:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )


# ===== 用户认证 =====

def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    验证用户凭据

    Args:
        username: 用户名
        password: 密码

    Returns:
        用户对象或 None
    """
    user_data = USERS_DB.get(username)
    if not user_data:
        return None

    if not pwd_context.verify(password, user_data["hashed_password"]):
        return None

    return User(
        username=user_data["username"],
        user_id=user_data["user_id"],
        email=user_data.get("email"),
        role=user_data["role"],
        permissions=user_data.get("permissions", [])
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """
    获取当前认证用户

    Args:
        credentials: HTTP Bearer 凭据

    Returns:
        当前用户对象

    Raises:
        HTTPException: 未认证或令牌无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = decode_token(token)

    # 验证令牌类型
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误"
        )

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效"
        )

    user_data = USERS_DB.get(username)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    return User(
        username=user_data["username"],
        user_id=user_data["user_id"],
        email=user_data.get("email"),
        role=user_data["role"],
        permissions=user_data.get("permissions", [])
    )


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[User]:
    """
    获取当前用户（可选）

    如果没有提供凭据或凭据无效，返回 None 而不是抛出异常

    Args:
        credentials: HTTP Bearer 凭据

    Returns:
        用户对象或 None
    """
    if credentials is None:
        return None

    try:
        return get_current_user(credentials)
    except HTTPException:
        return None


# ===== 权限检查 =====

def require_permissions(*permissions: str):
    """
    权限检查装饰器工厂

    Args:
        *permissions: 需要的权限列表

    Returns:
        依赖函数
    """
    def check_permissions(current_user: User = Depends(get_current_user)) -> User:
        """检查用户权限"""
        # 管理员拥有所有权限
        if current_user.role == "admin":
            return current_user

        # 检查用户是否拥有所需权限
        user_permissions = set(current_user.permissions or [])
        required_permissions = set(permissions)

        if not required_permissions.issubset(user_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下权限: {', '.join(required_permissions)}"
            )

        return current_user

    return Depends(check_permissions)


def require_role(*roles: str):
    """
    角色检查装饰器工厂

    Args:
        *roles: 允许的角色列表

    Returns:
        依赖函数
    """
    def check_role(current_user: User = Depends(get_current_user)) -> User:
        """检查用户角色"""
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}"
            )

        return current_user

    return Depends(check_role)


# ===== 登录/注册模型 =====

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名", min_length=1, max_length=50)
    password: str = Field(..., description="密码", min_length=1, max_length=100)


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class TokenRefreshRequest(BaseModel):
    """令牌刷新请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class TokenRefreshResponse(BaseModel):
    """令牌刷新响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    username: str
    email: Optional[str]
    role: str
    permissions: List[str]


# ===== 认证端点 =====

from fastapi import APIRouter
from datetime import timezone

auth_router = APIRouter(prefix="/auth", tags=["认证"])


@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录

    使用用户名和密码登录，返回访问令牌和刷新令牌。
    """
    user = authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 创建令牌
    token_data = {"sub": user.username, "user_id": user.user_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"用户 {user.username} 登录成功")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "permissions": user.permissions
        }
    )


@auth_router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: TokenRefreshRequest):
    """
    刷新访问令牌

    使用刷新令牌获取新的访问令牌。
    """
    try:
        payload = decode_token(request.refresh_token)

        # 验证令牌类型
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌类型错误"
            )

        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌无效"
            )

        # 验证用户仍然存在
        user_data = USERS_DB.get(username)
        if user_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        # 创建新的访问令牌
        token_data = {"sub": username, "user_id": user_data["user_id"]}
        access_token = create_access_token(token_data)

        logger.info(f"用户 {username} 刷新令牌成功")

        return TokenRefreshResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效"
        )


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前用户信息

    返回当前认证用户的详细信息。
    """
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        permissions=current_user.permissions or []
    )


@auth_router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    用户登出

    注: 无状态 JWT 实现中，登出主要在客户端处理（删除令牌）。
    服务端可以选择将令牌加入黑名单（需要 Redis 等支持）。
    """
    logger.info(f"用户 {current_user.username} 登出")

    return {
        "success": True,
        "message": "登出成功"
    }


__all__ = [
    "User",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "authenticate_user",
    "get_current_user",
    "get_current_user_optional",
    "require_permissions",
    "require_role",
    "LoginRequest",
    "LoginResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
    "UserResponse",
    "auth_router",
    "security",
]
