from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.auth.auth_service import AuthService
from app.core.auth.jwt import create_access_token
import datetime

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()

# ----- 요청 모델 -----
class SignupRequest(BaseModel):
    account_id: str
    password: str
    user_name: str

class LoginRequest(BaseModel):
    account_id: str
    password: str

# ----- 회원가입 -----
@router.post("/signup")
def signup(payload: SignupRequest):
    exists = service.get_user_by_account(payload.account_id)
    if exists:
        raise HTTPException(400, "이미 존재하는 사용자입니다.")

    user = service.create_user(
        account_id=payload.account_id,
        password=payload.password,
        user_name=payload.user_name,
    )
    return {"message": "회원가입 완료", "user": user}

# ----- 로그인 -----
@router.post("/login")
def login(payload: LoginRequest):
    # 1) 사용자 조회
    user = service.get_user_by_account(payload.account_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    # 2) 비밀번호 검증
    if not service.verify_password(payload.password, user["password"]):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    # 3) JWT 생성
    access_token = create_access_token(
        data={"user_id": user["id"]}  # payload
    )

    # 4) password 제거하고 user 정보 가공
    safe_user = {
        "id": user["id"],
        "account_id": user["account_id"],
        "user_name": user["user_name"],
        "role": user["role"],
        "dept_id": user["dept_id"],
        "project_id": user.get("project_id"),
        "profile_image_path": user.get("profile_image_path"),
    }

    # 5) 최종 응답
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": safe_user,
    }
