# app/services/admin/project_permission_service.py
from app.core.db import get_connection

class ProjectPermissionService:
    def __init__(self):
        pass

    def get_owner_dept(self, project_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT dept_id FROM projects WHERE project_id = %s",
                    (project_id,)
                )
                row = cur.fetchone()
                return row["dept_id"] if row else None
        finally:
            db.close()

    def update_permissions(self, project_id: int, dept_ids: list[int]):
        """
        프로젝트 협업 부서 전체 재설정
        """
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "DELETE FROM project_depts WHERE project_id = %s",
                    (project_id,)
                )

                for dept_id in dept_ids:
                    cur.execute(
                        "INSERT INTO project_depts (project_id, dept_id) VALUES (%s, %s)",
                        (project_id, dept_id)
                    )

            db.commit()
            return True
        finally:
            db.close()

    def list_permissions(self, project_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT dept_id FROM project_depts WHERE project_id = %s",
                    (project_id,)
                )
                rows = cur.fetchall()
                return [r["dept_id"] for r in rows]
        finally:
            db.close()
