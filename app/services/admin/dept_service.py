# app/services/admin/dept_service.py
from app.core.db import get_connection

class DeptService:
    def __init__(self):
        pass

    def list(self):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM dept ORDER BY id DESC")
                return cur.fetchall()
        finally:
            db.close()

    def create(self, name: str, description: str = None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO dept (dept_name, description) VALUES (%s, %s)",
                    (name, description)
                )
                db.commit()
                return cur.lastrowid
        finally:
            db.close()

    def update(self, dept_id: int, name: str, description: str = None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    UPDATE dept 
                    SET dept_name=%s, description=%s
                    WHERE id=%s
                """
                cur.execute(sql, (name, description, dept_id))
                db.commit()
                return cur.rowcount
        finally:
            db.close()

    def delete(self, dept_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("DELETE FROM dept WHERE id=%s", (dept_id,))
                db.commit()
                return cur.rowcount
        finally:
            db.close()
