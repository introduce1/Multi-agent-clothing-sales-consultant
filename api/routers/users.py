# -*- coding: utf-8 -*-
"""
用户管理API路由
提供用户注册、登录、信息管理等功能
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
import bcrypt
import jwt

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer()
beijing_tz = timezone(timedelta(hours=8))

# JWT配置
JWT_SECRET = "your-secret-key"  # 在生产环境中应该从环境变量获取
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class UserRegister(BaseModel):
    """用户注册模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    phone: Optional[str] = Field(None, max_length=20, description="电话号码")
    role: str = Field("customer", description="用户角色")


class UserLogin(BaseModel):
    """用户登录模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserProfile(BaseModel):
    """用户资料模型"""
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool = True
    created_at: str
    last_login: Optional[str] = None
    preferences: Dict[str, Any] = {}


class UserUpdate(BaseModel):
    """用户更新模型"""
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    preferences: Optional[Dict[str, Any]] = None


class PasswordChange(BaseModel):
    """密码修改模型"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class AuthResponse(BaseModel):
    """认证响应模型"""
    success: bool
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class UserListResponse(BaseModel):
    """用户列表响应模型"""
    success: bool
    users: List[UserProfile]
    total_count: int
    page: int
    page_size: int


# 模拟用户数据库（在实际项目中应该使用真实数据库）
users_db = {}


def hash_password(password: str) -> str:
    """密码哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(user_id: str, username: str, role: str) -> str:
    """创建访问令牌"""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """验证访问令牌"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已过期"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的token"
        )


def get_current_user(token_payload: Dict[str, Any] = Depends(verify_token)) -> UserProfile:
    """获取当前用户"""
    user_id = token_payload.get("user_id")
    if not user_id or user_id not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user_data = users_db[user_id]
    return UserProfile(**user_data)


@router.post("/register", response_model=AuthResponse)
async def register_user(user_data: UserRegister):
    """用户注册"""
    try:
        # 检查用户名和邮箱是否已存在
        for existing_user in users_db.values():
            if existing_user["username"] == user_data.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户名已存在"
                )
            if existing_user["email"] == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被注册"
                )
        
        # 创建新用户
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(user_data.password)
        
        new_user = {
            "user_id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "password": hashed_password,
            "full_name": user_data.full_name,
            "phone": user_data.phone,
            "role": user_data.role,
            "is_active": True,
            "created_at": datetime.now(beijing_tz).isoformat(),
            "last_login": None,
            "preferences": {}
        }
        
        users_db[user_id] = new_user
        
        # 生成访问令牌
        access_token = create_access_token(user_id, user_data.username, user_data.role)
        
        # 创建用户资料对象
        user_profile = UserProfile(**{k: v for k, v in new_user.items() if k != "password"})
        
        logger.info(f"用户注册成功: {user_data.username}")
        
        return AuthResponse(
            success=True,
            access_token=access_token,
            expires_in=JWT_EXPIRATION_HOURS * 3600,
            user=user_profile
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(login_data: UserLogin):
    """用户登录"""
    try:
        # 查找用户（支持用户名或邮箱登录）
        user = None
        for user_data in users_db.values():
            if (user_data["username"] == login_data.username or 
                user_data["email"] == login_data.username):
                user = user_data
                break
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 验证密码
        if not verify_password(login_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 检查用户是否激活
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账户已被禁用"
            )
        
        # 更新最后登录时间
        user["last_login"] = datetime.now(beijing_tz).isoformat()
        
        # 生成访问令牌
        access_token = create_access_token(user["user_id"], user["username"], user["role"])
        
        # 创建用户资料对象
        user_profile = UserProfile(**{k: v for k, v in user.items() if k != "password"})
        
        logger.info(f"用户登录成功: {user['username']}")
        
        return AuthResponse(
            success=True,
            access_token=access_token,
            expires_in=JWT_EXPIRATION_HOURS * 3600,
            user=user_profile
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(current_user: UserProfile = Depends(get_current_user)):
    """获取用户资料"""
    return current_user


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    update_data: UserUpdate,
    current_user: UserProfile = Depends(get_current_user)
):
    """更新用户资料"""
    try:
        user_data = users_db[current_user.user_id]
        
        # 更新字段
        if update_data.full_name is not None:
            user_data["full_name"] = update_data.full_name
        if update_data.phone is not None:
            user_data["phone"] = update_data.phone
        if update_data.preferences is not None:
            user_data["preferences"].update(update_data.preferences)
        
        # 返回更新后的用户资料
        updated_profile = UserProfile(**{k: v for k, v in user_data.items() if k != "password"})
        
        logger.info(f"用户资料更新成功: {current_user.username}")
        
        return updated_profile
        
    except Exception as e:
        logger.error(f"用户资料更新失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失败，请稍后重试"
        )


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: UserProfile = Depends(get_current_user)
):
    """修改密码"""
    try:
        user_data = users_db[current_user.user_id]
        
        # 验证当前密码
        if not verify_password(password_data.current_password, user_data["password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码错误"
            )
        
        # 更新密码
        user_data["password"] = hash_password(password_data.new_password)
        
        logger.info(f"用户密码修改成功: {current_user.username}")
        
        return {"success": True, "message": "密码修改成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"密码修改失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败，请稍后重试"
        )


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    current_user: UserProfile = Depends(get_current_user)
):
    """获取用户列表（需要管理员权限）"""
    # 检查权限
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    try:
        # 过滤用户
        filtered_users = []
        for user_data in users_db.values():
            if role and user_data["role"] != role:
                continue
            
            user_profile = UserProfile(**{k: v for k, v in user_data.items() if k != "password"})
            filtered_users.append(user_profile)
        
        # 分页
        total_count = len(filtered_users)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_users = filtered_users[start_idx:end_idx]
        
        return UserListResponse(
            success=True,
            users=paginated_users,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )


@router.post("/logout")
async def logout_user(current_user: UserProfile = Depends(get_current_user)):
    """用户登出"""
    # 在实际项目中，可能需要将token加入黑名单
    logger.info(f"用户登出: {current_user.username}")
    return {"success": True, "message": "登出成功"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: UserProfile = Depends(get_current_user)
):
    """删除用户（需要管理员权限）"""
    # 检查权限
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    if user_id not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 不能删除自己
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )
    
    try:
        deleted_user = users_db.pop(user_id)
        logger.info(f"用户删除成功: {deleted_user['username']}")
        
        return {"success": True, "message": "用户删除成功"}
        
    except Exception as e:
        logger.error(f"用户删除失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户删除失败"
        )