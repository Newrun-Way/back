from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.auth.auth_service import AuthService

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
    # 아이디 중복 확인
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
    user = service.get_user_by_account(payload.account_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    if not service.verify_password(payload.password, user["password"]):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    # JWT 필요 시 여기서 발급
    return {
        "message": "로그인 성공",
        "user": {
            "id": user["id"],
            "account_id": user["account_id"],
            "user_name": user["user_name"],
            "role": user["role"],
            "dept_id": user["dept_id"],
            "project_id": user["project_id"],
        }
    }
