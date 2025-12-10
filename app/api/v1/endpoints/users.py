# app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil
from app.api.v1.endpoints.auth import get_current_user   # ← 중요!
from app.services.user.user_service import UserService
from app.core.config import get_settings

router = APIRouter(prefix="/users", tags=["Users"])
service = UserService()
settings = get_settings()


# -----------------------------------------------------
# 내 정보 조회
# -----------------------------------------------------
@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = dict(current_user)
    user.pop("password", None)
    return user


# -----------------------------------------------------
# 내 정보 수정
# -----------------------------------------------------
class UpdateMe(BaseModel):
    user_name: str | None = None
    nickname: str | None = None

@router.put("/me")
def update_me(payload: UpdateMe, current_user: dict = Depends(get_current_user)):
    fields = {k: v for k, v in payload.dict().items() if v is not None}

    updated = service.update_user(current_user["id"], fields)
    if not updated:
        raise HTTPException(400, "Failed to update user")

    updated.pop("password", None)
    return updated


# -----------------------------------------------------
# 비밀번호 변경
# -----------------------------------------------------
class PasswordChange(BaseModel):
    old_password: str
    new_password: str

@router.put("/me/password")
def change_password(payload: PasswordChange, current_user: dict = Depends(get_current_user)):
    ok = service.update_password(
        current_user["id"],
        payload.old_password,
        payload.new_password,
    )

    if ok is False:
        raise HTTPException(400, "기존 비밀번호가 일치하지 않습니다.")

    return {"message": "비밀번호가 변경되었습니다."}


# -----------------------------------------------------
# 프로필 이미지 업로드
# -----------------------------------------------------
@router.post("/me/profile")
def upload_profile_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]

    # 저장 경로
    save_dir = Path(settings.DATA_DIR) / "profile"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{user_id}_{file.filename}"

    # 파일 저장
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # DB 업데이트
    updated = service.update_user(user_id, {"profile_image_path": str(save_path)})
    return {"message": "업로드 성공", "profile_image_path": updated["profile_image_path"]}
