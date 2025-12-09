#app/services/auth/auth_service.py
from app.core.db import get_connection
import bcrypt

class AuthService:
    # ----------------------------------------------------
    # 비밀번호 해시/검증
    # ----------------------------------------------------
    def hash_password(self, raw_pw: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(raw_pw.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, raw_pw: str, hashed_pw: str) -> bool:
        return bcrypt.checkpw(raw_pw.encode("utf-8"), hashed_pw.encode("utf-8"))

    # ----------------------------------------------------
    # 사용자 조회
    # ----------------------------------------------------
    def get_user_by_account(self, account_id: str):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE account_id=%s",
                    (account_id,),
                )
                return cur.fetchone()
        finally:
            db.close()

    def get_user_by_id(self, user_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM users WHERE id=%s",
                    (user_id,),
                )
                return cur.fetchone()
        finally:
            db.close()

    # ----------------------------------------------------
    # 사용자 생성
    # ----------------------------------------------------
    def create_user(self, account_id: str, password: str, user_name: str):
        hashed_pw = self.hash_password(password)
        db = get_connection()

        try:
            with db.cursor() as cur:
                sql = """
                    INSERT INTO users (account_id, password, user_name, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """
                cur.execute(sql, (account_id, hashed_pw, user_name))
                db.commit()
        finally:
            db.close()

        # 후속 조회는 get_user_by_account에서 자체적으로 DB 열고 닫음
        return self.get_user_by_account(account_id)

    # ----------------------------------------------------
    # 안전한 사용자 출력용 변환
    # ----------------------------------------------------
    def to_safe_user(self, user: dict | None) -> dict | None:
        if not user:
            return None

        return {
            "id": user["id"],
            "account_id": user["account_id"],
            "user_name": user.get("user_name"),
            "role": user.get("role"),
            "dept_id": user.get("dept_id"),
            "project_id": user.get("project_id"),
            "profile_image_path": user.get("profile_image_path"),
        }
