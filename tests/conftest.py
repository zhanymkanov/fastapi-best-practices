"""测试 conftest —— MongoDB + Beanie 测试 fixtures"""

from collections.abc import AsyncGenerator # 导入 AsyncGenerator 类型

import pytest_asyncio # 导入 pytest_asyncio 模块
from beanie import init_beanie # 导入 init_beanie 模块
from httpx import ASGITransport, AsyncClient # 导入 ASGITransport, AsyncClient 模块
from motor.motor_asyncio import AsyncIOMotorClient # 导入 AsyncIOMotorClient 模块
from passlib.hash import bcrypt # 导入 bcrypt 模块

from app.core.config import settings # 导入 settings 模块
from app.core.security import create_access_token # 导入 create_access_token 模块
from app.main import app # 导入 app 模块
from app.models.audit_log import AuditLog
from app.models.device import Device # 导入 Device 模型
from app.models.permission import RolePermission
from app.models.tenant import Tenant # 导入 Tenant 模型
from app.models.user import User # 导入 User 模型

TEST_DB_NAME = "test_petchill" # 测试数据库名称


@pytest_asyncio.fixture(scope="session") # 全局 MongoDB 客户端
async def mongodb_client(): # 全局 MongoDB 客户端
    """全局 MongoDB 客户端""" 
    client = AsyncIOMotorClient(settings.MONGODB_URL) # 创建 MongoDB 客户端
    yield client # 返回 MongoDB 客户端
    client.close() # 关闭 MongoDB 客户端


@pytest_asyncio.fixture(scope="session", autouse=True) # 初始化 Beanie 测试数据库，所有测试结束后清理
async def init_test_db(mongodb_client): # 初始化 Beanie 测试数据库，所有测试结束后清理
    """初始化 Beanie 测试数据库，所有测试结束后清理"""
    db = mongodb_client[TEST_DB_NAME] # 创建测试数据库
    await init_beanie(
        database=db,
        document_models=[Tenant, User, Device, RolePermission, AuditLog],  # 注册模型
    )
    yield
    await mongodb_client.drop_database(TEST_DB_NAME) # 删除测试数据库


@pytest_asyncio.fixture(scope="module") # 异步测试客户端
async def async_client() -> AsyncGenerator[AsyncClient, None]: # 异步测试客户端
    """htpx 异步测试客户端"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test" # 创建测试客户端
    ) as ac:
        yield ac # 返回测试客户端


@pytest_asyncio.fixture # 清理集合
async def clean_collections():
    """每个测试后清理集合"""
    yield
    await User.find_all().delete_many()
    await Tenant.find_all().delete_many()
    await Device.find_all().delete_many()
    await RolePermission.find_all().delete_many()
    await AuditLog.find_all().delete_many()


@pytest_asyncio.fixture # 创建管理员用户并返回
async def admin_user(clean_collections) -> User:
    """创建管理员用户并返回"""
    user = User(
        tenant_id="test-tenant-id",
        username="admin",
        email="admin@petchill.com",
        hashed_password=bcrypt.hash("Admin123!"),
        role="admin",
        is_active=True,
    )
    return await user.insert()


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    """生成管理员 JWT token"""
    return create_access_token(subject=str(admin_user.id), extra_claims={"role": "admin"})


@pytest_asyncio.fixture # 管理员 Authorization headers
def admin_headers(admin_token: str) -> dict:
    """管理员 Authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture # 创建普通成员用户并返回
async def member_user(clean_collections) -> User:
    """创建普通成员用户"""
    user = User(
        tenant_id="test-tenant-id",
        username="member",
        email="member@petchill.com",
        hashed_password=bcrypt.hash("Member123!"),
        role="member",
        is_active=True,
    )
    return await user.insert()


@pytest_asyncio.fixture # 生成普通成员 JWT token
async def member_token(member_user: User) -> str:
    """生成普通成员 JWT token"""
    return create_access_token(subject=str(member_user.id), extra_claims={"role": "member"})


@pytest_asyncio.fixture # 普通成员 Authorization headers
def member_headers(member_token: str) -> dict:
    """普通成员 Authorization headers"""
    return {"Authorization": f"Bearer {member_token}"} # 返回普通成员 Authorization headers
