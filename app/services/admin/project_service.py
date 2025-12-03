# app/services/admin/project_service.py
from app.core.db import get_connection

class ProjectService:
    def __init__(self):
        pass

    def list(self):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM projects ORDER BY project_id DESC")
                return cur.fetchall()
        finally:
            db.close()

    def create(self, name: str, dept_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO projects (project_name, dept_id) VALUES (%s, %s)",
                    (name, dept_id)
                )
                db.commit()
                return cur.lastrowid
        finally:
            db.close()

    def update(self, project_id: int, name: str, dept_id: int, status: str | None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    UPDATE projects
                    SET project_name=%s,
                        dept_id=%s,
                        status=COALESCE(%s, status)
                    WHERE project_id=%s
                """
                cur.execute(sql, (name, dept_id, status, project_id))
                db.commit()
                return cur.rowcount
        finally:
            db.close()

    def delete(self, project_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))
                db.commit()
                return cur.rowcount
        finally:
            db.close()

    def get_by_dept_id(self, dept_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    SELECT project_id, project_name, dept_id, status
                    FROM projects 
                    WHERE dept_id = %s
                """
                cur.execute(sql, (dept_id,))
                rows = cur.fetchall()

                return [
                    {
                        "project_id": row["project_id"],
                        "project_name": row["project_name"],
                        "dept_id": row["dept_id"],
                        "status": row["status"]
                    }
                    for row in rows
                ]
        finally:
            db.close()
