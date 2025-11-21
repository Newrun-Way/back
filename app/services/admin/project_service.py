from app.core.db import get_connection

class ProjectService:
    def __init__(self):
        self.db = get_connection()

    def list(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM projects ORDER BY id DESC")
            return cur.fetchall()

    def create(self, name: str, dept_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (project_name, dept_id) VALUES (%s, %s)",
                (name, dept_id)
            )
            self.db.commit()
            return cur.lastrowid

    def update(self, project_id: int, name: str, dept_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE projects SET project_name=%s, dept_id=%s WHERE project_id=%s",
                (name, dept_id, project_id)
            )
            self.db.commit()
            return cur.rowcount

    def delete(self, project_id: int):
        with self.db.cursor() as cur:
            # id -> project_id로 변경
            cur.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))
            self.db.commit()
            return cur.rowcount

    def get_by_dept_id(self, dept_id: int):
        with self.db.cursor() as cur:
            sql = """
                SELECT project_id, project_name, dept_id
                FROM projects 
                WHERE dept_id = %s
            """
            cur.execute(sql, (dept_id,))
            rows = cur.fetchall()

            return [
                {
                    "project_id": row[0],
                    "project_name": row[1],
                    "dept_id": row[2],
                }
                for row in rows
            ]