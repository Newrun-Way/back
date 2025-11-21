from app.core.db import get_connection

class DeptService:
    def __init__(self):
        self.db = get_connection()

    def list(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM dept ORDER BY id DESC")
            return cur.fetchall()

    def create(self, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO dept (dept_name, description) VALUES (%s, %s)",
                (name,description)
            )
            self.db.commit()
            return cur.lastrowid

    def update(self, dept_id: int, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE dept SET dept_name=%s, description=%s, WHERE id=%s",
                (name,description, dept_id)
            )
            self.db.commit()
            return cur.rowcount

    def delete(self, dept_id: int):
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM dept WHERE id=%s", (dept_id,))
            self.db.commit()
            return cur.rowcount
