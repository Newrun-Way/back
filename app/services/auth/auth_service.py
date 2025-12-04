from app.core.db import get_connection
from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__ident="2b",
    deprecated="auto",
)

class AuthService:
    def __init__(self):
        self.db = get_connection()

    def hash_password(self, raw_pw: str) -> str:
        return pwd_context.hash(raw_pw)

    def verify_password(self, raw_pw: str, hashed_pw: str) -> bool:
        return pwd_context.verify(raw_pw, hashed_pw)

    def get_user_by_account(self, account_id: str):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE account_id=%s", (account_id,))
            return cur.fetchone()

    def create_user(self, account_id: str, password: str, user_name: str):
        hashed_pw = self.hash_password(password)

        with self.db.cursor() as cur:
            sql = """
            INSERT INTO users (account_id, password, user_name, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            """
            cur.execute(sql, (account_id, hashed_pw, user_name))
            self.db.commit()

            return self.get_user_by_account(account_id)
