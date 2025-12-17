from app.core.db import get_connection
from datetime import datetime
import bcrypt

class UserService:

    # -----------------------------
    # 사번(employee_id) 생성
    # -----------------------------
    def generate_employee_id(self, user_pk: int, dept_id: int) -> str:
        year = datetime.now().year
        dept_str = f"{dept_id:02d}"
        return f"{year}{dept_str}{user_pk}"

    # -----------------------------
    # 사용자 생성
    # -----------------------------
    def create_user(self, account_id, password_hash, user_name, dept_id, role):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    INSERT INTO users
                    (account_id, password, user_name, dept_id, role, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 1, NOW(), NOW())
                """, (account_id, password_hash, user_name, dept_id, role))
                user_pk = cur.lastrowid
                db.commit()

            employee_id = self.generate_employee_id(user_pk, dept_id)

            with db.cursor() as cur:
                cur.execute(
                    "UPDATE users SET employee_id=%s WHERE id=%s",
                    (employee_id, user_pk)
                )
                db.commit()

            return self.get_by_id(user_pk)
        finally:
            db.close()

    # -----------------------------
    # 단일 조회 (활성 유저만)
    # -----------------------------
    def get_by_id(self, user_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT *
                    FROM users
                    WHERE id=%s AND is_active=1
                """, (user_id,))
                return cur.fetchone()
        finally:
            db.close()

    def get_by_account(self, account_id: str):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT *
                    FROM users
                    WHERE account_id=%s AND is_active=1
                """, (account_id,))
                return cur.fetchone()
        finally:
            db.close()

    # -----------------------------
    # 전체 조회 (삭제 유저 제외 ✅)
    # -----------------------------
    def list_all(self):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT *
                    FROM users
                    WHERE is_active = 1
                    ORDER BY id DESC
                """)
                return cur.fetchall()
        finally:
            db.close()

    # -----------------------------
    # 수정
    # -----------------------------
    def update_user(self, user_id: int, fields: dict):
        db = get_connection()
        try:
            set_clause = ", ".join([f"{k}=%s" for k in fields.keys()])
            params = list(fields.values()) + [user_id]

            with db.cursor() as cur:
                cur.execute(
                    f"UPDATE users SET {set_clause}, updated_at=NOW() WHERE id=%s",
                    params
                )
                db.commit()

            return self.get_by_id(user_id)
        finally:
            db.close()

    # -----------------------------
    # 삭제 (Soft Delete)
    # -----------------------------
    def deactivate_user(self, user_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE users
                    SET is_active=0, updated_at=NOW()
                    WHERE id=%s
                """, (user_id,))
                db.commit()
            return {"message": "User deactivated", "user_id": user_id}
        finally:
            db.close()

    # -----------------------------
    # 비밀번호 변경
    # -----------------------------
    def update_password(self, user_id: int, old_pw: str, new_pw: str):
        user = self.get_by_id(user_id)
        if not user:
            return None

        if not bcrypt.checkpw(old_pw.encode(), user["password"].encode()):
            return False

        hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()

        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE users
                    SET password=%s, updated_at=NOW()
                    WHERE id=%s
                """, (hashed, user_id))
                db.commit()
            return True
        finally:
            db.close()
