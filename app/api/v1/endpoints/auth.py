# app/api/v1/endpoints/auth.py

from fastapi import APIRouter, HTTPException, Header, Depends
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

# ============================================================
#  JWT 기반 인증 Dependency (핵심!)
# ============================================================

def get_current_user(authorization: str = Header(None)):
    """
    Authorization: Bearer <token>
    → decode_token()
    → DB에서 user 조회
    → 성공하면 user dict 반환
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    payload = decode_token(token)

    user = service.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    return user


# ============================================================
#  Pydantic Models (Swagger Example 포함)
# ============================================================

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


# --- Login ------------------------------------------

class LoginRequest(BaseModel):
    account_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/login", response_model=LoginResponse, summary="로그인")
def login(payload: LoginRequest):
    user = service.get_user_by_account(payload.account_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    if not service.verify_password(payload.password, user["password"]):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    base_claim = {"user_id": user["id"]}

    access_token = create_access_token(base_claim)
    refresh_token = create_refresh_token(base_claim)

    safe_user = service.to_safe_user(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": safe_user,
    }


# --- Token Refresh -----------------------------------

class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh_token(payload: TokenRefreshRequest):
    token = payload.refresh_token
    decoded = decode_token(token)

    if not is_refresh_token(decoded):
        raise HTTPException(401, "Refresh token이 아닙니다.")

    new_access = create_access_token({"user_id": decoded["user_id"]})

    return {"access_token": new_access, "token_type": "bearer"}


# ============================================================
#  로그인된 유저 세션 확인 (옵션)
# ============================================================

@router.get("/me", response_model=UserOut, summary="현재 로그인된 유저 정보 조회")
def auth_me(current_user: dict = Depends(get_current_user)):
    return service.to_safe_user(current_user)
