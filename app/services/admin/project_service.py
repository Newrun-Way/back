from app.core.db import get_connection

class ProjectService:
    def __init__(self):
        self.db = get_connection()

    def list(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM project ORDER BY id DESC")
            return cur.fetchall()

    def create(self, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO project (project_name) VALUES (%s)",
                (name,)
            )
            self.db.commit()
            return cur.lastrowid

    def update(self, project_id: int, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE project SET project_name=%s WHERE id=%s",
                (name, project_id)
            )
            self.db.commit()
            return cur.rowcount

    def delete(self, project_id: int):
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM project WHERE id=%s", (project_id,))
            self.db.commit()
            return cur.rowcount
