from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import bcrypt
from app.services.user.user_service import UserService

router = APIRouter(prefix="/admin/users", tags=["Admin Users"])
service = UserService()


# -------------------------
# 요청 모델 정의
# -------------------------
class AdminUserCreate(BaseModel):
    account_id: str
    password: str
    user_name: str
    dept_id: int
    role: str = "USER"   # USER / MANAGER / SUPER_ADMIN


class AdminUserUpdate(BaseModel):
    user_name: str | None = None
    dept_id: int | None = None
    role: str | None = None


# -------------------------
# 사용자 생성
# -------------------------
@router.post("/")
def create_user(payload: AdminUserCreate):

    # 중복 계정 체크
    exists = service.get_by_account(payload.account_id)
    if exists:
        raise HTTPException(400, "이미 존재하는 account_id 입니다.")

    # 비밀번호 해싱
    hashed = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user = service.create_user(
        account_id=payload.account_id,
        password_hash=hashed,
        user_name=payload.user_name,
        dept_id=payload.dept_id,
        role=payload.role,
    )

    # password 제거 후 반환
    user.pop("password", None)

    return {
        "message": "사용자 생성 완료",
        "user": user
    }


# -------------------------
# 전체 조회
# -------------------------
@router.get("/")
def list_users():
    users = service.list_all()

    # password는 제거
    for u in users:
        u.pop("password", None)

    return users


# -------------------------
# 단일 사용자 조회
# -------------------------
@router.get("/{user_id}")
def get_user(user_id: int):
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.pop("password", None)
    return user


# -------------------------
# 사용자 수정
# -------------------------
@router.put("/{user_id}")
def update_user(user_id: int, payload: AdminUserUpdate):
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    fields = {k: v for k, v in payload.dict().items() if v is not None}
    updated = service.update_user(user_id, fields)

    updated.pop("password", None)
    return updated


# -------------------------
# 사용자 비활성화 (삭제)
# -------------------------
@router.delete("/{user_id}")
def delete_user(user_id: int):
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return service.deactivate_user(user_id)
