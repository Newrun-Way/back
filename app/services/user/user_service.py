from app.core.db import get_connection
from datetime import datetime

class UserService:
    def __init__(self):
        self.db = get_connection()

    # -----------------------------
    # 사번(employee_id) 생성 함수
    # -----------------------------
    def generate_employee_id(self, user_pk: int, dept_id: int) -> str:
        year = datetime.now().year
        dept_str = f"{dept_id:02d}"   # 2자리 dept
        return f"{year}{dept_str}{user_pk}"

    # -----------------------------
    # 사용자 생성 (관리자용)
    # -----------------------------
    def create_user(self, account_id, password_hash, user_name, dept_id, role):
        with self.db.cursor() as cur:
            sql = """
            INSERT INTO users (account_id, password, user_name, dept_id, role, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """
            cur.execute(sql, (account_id, password_hash, user_name, dept_id, role))
            self.db.commit()

            user_pk = cur.lastrowid

        # 사번(employee_id) 생성 후 저장
        employee_id = self.generate_employee_id(user_pk, dept_id)

        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE users SET employee_id=%s WHERE id=%s",
                (employee_id, user_pk)
            )
            self.db.commit()

        return self.get_by_id(user_pk)

    # -----------------------------
    # 단일 조회
    # -----------------------------
    def get_by_id(self, user_id: int):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return cur.fetchone()

    def get_by_account(self, account_id: str):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE account_id=%s", (account_id,))
            return cur.fetchone()

    # -----------------------------
    # 전체 조회
    # -----------------------------
    def list_all(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY id DESC")
            return cur.fetchall()

    # -----------------------------
    # 수정 (name, role, dept 등)
    # -----------------------------
    def update_user(self, user_id: int, fields: dict):
        set_clause = ", ".join([f"{k}=%s" for k in fields.keys()])
        params = list(fields.values()) + [user_id]

        with self.db.cursor() as cur:
            cur.execute(f"UPDATE users SET {set_clause}, updated_at=NOW() WHERE id=%s", params)
            self.db.commit()

        return self.get_by_id(user_id)

    # -----------------------------
    # 삭제 (is_active = 0 처리)
    # -----------------------------
    def deactivate_user(self, user_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_active=0, updated_at=NOW() WHERE id=%s",
                (user_id,)
            )
            self.db.commit()
        return {"message": "User deactivated", "user_id": user_id}
