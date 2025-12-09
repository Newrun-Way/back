from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal

from app.services.auth.auth_service import AuthService
from app.core.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    is_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()


# ============================================
# Pydantic Models (Swagger Example 포함)
# ============================================

class UserOut(BaseModel):
    id: int
    account_id: str
    user_name: str
    role: Literal["SUPER_ADMIN", "MANAGER", "USER"] | str
    dept_id: Optional[int] = None
    project_id: Optional[int] = None
    profile_image_path: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "account_id": "user123",
                "user_name": "홍길동",
                "role": "USER",
                "dept_id": 2,
                "project_id": 5,
                "profile_image_path": None,
            }
        }


# --- Signup ----------------------------------------

class SignupRequest(BaseModel):
    account_id: str = Field(..., example="new_user")
    password: str = Field(..., example="P@ssw0rd!")
    user_name: str = Field(..., example="홍길동")


class SignupResponse(BaseModel):
    message: str
    user: UserOut

    class Config:
        json_schema_extra = {
            "example": {
                "message": "회원가입 완료",
                "user": UserOut.Config.json_schema_extra["example"],
            }
        }


# --- Login ------------------------------------------

class LoginRequest(BaseModel):
    account_id: str = Field(..., example="user123")
    password: str = Field(..., example="비밀번호123!")


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJh...",
                "token_type": "bearer",
                "user": UserOut.Config.json_schema_extra["example"],
            }
        }


# --- Token Refresh -----------------------------------

class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIs...")


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "새로운-access-token",
                "token_type": "bearer",
            }
        }


# ============================================
# 엔드포인트
# ============================================

# 회원가입
@router.post("/signup", response_model=SignupResponse, summary="회원가입")
def signup(payload: SignupRequest):
    exists = service.get_user_by_account(payload.account_id)
    if exists:
        raise HTTPException(400, "이미 존재하는 사용자입니다.")

    user = service.create_user(
        account_id=payload.account_id,
        password=payload.password,
        user_name=payload.user_name,
    )

    safe_user = service.to_safe_user(user)

    return {
        "message": "회원가입 완료",
        "user": safe_user,
    }


# 로그인
@router.post("/login", response_model=LoginResponse, summary="로그인")
def login(payload: LoginRequest):
    # 1) 사용자 조회
    user = service.get_user_by_account(payload.account_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    # 2) 비밀번호 확인
    if not service.verify_password(payload.password, user["password"]):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    # 3) JWT 발급
    base_claim = {"user_id": user["id"]}

    access_token = create_access_token(base_claim)
    refresh_token = create_refresh_token(base_claim)

    # 4) user 출력 정리
    safe_user = service.to_safe_user(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": safe_user,
    }


# Access Token 재발급
@router.post("/refresh", response_model=TokenRefreshResponse, summary="Access Token 재발급")
def refresh_token(payload: TokenRefreshRequest):
    decoded = decode_token(payload.refresh_token)

    if not is_refresh_token(decoded):
        raise HTTPException(401, "유효한 Refresh Token이 아닙니다.")

    user_id = decoded.get("user_id")
    if not user_id:
        raise HTTPException(401, "토큰 정보가 유효하지 않습니다.")

    # 유저 존재 확인 (보안상 추가)
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    # 새 access token 발급
    new_access = create_access_token({"user_id": user_id})

    return {
        "access_token": new_access,
        "token_type": "bearer",
    }
