#app/api/v1/endpoints/users.py
from fastapi import APIRouter, Header, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.services.user.user_service import UserService
from app.core.auth.jwt import decode_token

router = APIRouter(prefix="/users", tags=["Users"])
service = UserService()


# --------------------------
# 유저 인증 도우미 함수
# --------------------------
def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")

    token = authorization.split(" ")[1]
    payload = decode_token(token)

    user = service.get_by_id(payload["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    return user


# --------------------------
# 내 정보 조회
# --------------------------
@router.get("/me")
def get_me(current_user: dict = get_current_user):
    current_user.pop("password", None)
    return current_user


# --------------------------
# 내 정보 수정
# --------------------------
class UpdateMe(BaseModel):
    user_name: str | None = None
    nickname: str | None = None

@router.put("/me")
def update_me(payload: UpdateMe, current_user: dict = get_current_user):
    fields = {k: v for k, v in payload.dict().items() if v is not None}

    updated = service.update_user(current_user["id"], fields)
    updated.pop("password", None)
    return updated


# --------------------------
# 비밀번호 변경
# --------------------------
class PasswordChange(BaseModel):
    old_password: str
    new_password: str

@router.put("/me/password")
def change_password(payload: PasswordChange, current_user: dict = get_current_user):

    result = service.update_password(
        current_user["id"],
        payload.old_password,
        payload.new_password
    )

    if result is False:
        raise HTTPException(400, "기존 비밀번호가 올바르지 않습니다.")

    return {"message": "비밀번호가 변경되었습니다."}


# --------------------------
# 프로필 이미지 업로드
# --------------------------
@router.post("/me/profile")
def upload_profile_image(
    file: UploadFile = File(...),
    current_user: dict = get_current_user
):
    # 파일 저장 경로 설정
    save_path = f"data/profile/{current_user['id']}_{file.filename}"

    # 실제 저장
    with open(save_path, "wb") as f:
        f.write(file.file.read())

    # DB 업데이트
    service.update_user(current_user["id"], {"profile_image_path": save_path})

    return {
        "message": "프로필 이미지 업데이트 완료",
        "path": save_path
    }
