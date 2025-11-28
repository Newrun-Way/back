from app.core.db import get_connection

class ProjectService:
    def __init__(self):
        self.db = get_connection()

    def list(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM projects ORDER BY project_id DESC")
            return cur.fetchall()

    def create(self, name: str, dept_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (project_name, dept_id) VALUES (%s, %s)",
                (name, dept_id)
            )
            self.db.commit()
            return cur.lastrowid

    def update(self, project_id: int, name: str, dept_id: int, status: str | None):
        with self.db.cursor() as cur:
            sql = """
                UPDATE projects
                SET project_name = %s,
                    dept_id = %s,
                    status = COALESCE(%s, status)   -- status가 None이면 기존 값 유지
                WHERE project_id = %s
            """

            cur.execute(sql, (name, dept_id, status, project_id))
            self.db.commit()
            return cur.rowcount

    def delete(self, project_id: int):
        with self.db.cursor() as cur:
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
                    "project_id": row["project_id"],    # row[0] -> row["project_id"]
                    "project_name": row["project_name"],# row[1] -> row["project_name"]
                    "dept_id": row["dept_id"],          # row[2] -> row["dept_id"]
                }
                for row in rows
            ]