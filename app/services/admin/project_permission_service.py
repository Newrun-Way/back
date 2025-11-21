from app.core.db import get_connection

class ProjectPermissionService:
    def __init__(self):
        self.db = get_connection()

    def get_owner_dept(self, project_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT dept_id FROM projects WHERE id = %s",
                (project_id,)
            )
            row = cur.fetchone()
            return row["dept_id"] if row else None

    def update_permissions(self, project_id: int, dept_ids: list[int]):
        """협업 부서 목록 전체 재설정 (owner_dept는 유지)"""

        # 먼저 기존 협업 부서 모두 제거
        with self.db.cursor() as cur:
            cur.execute(
                "DELETE FROM project_depts WHERE project_id = %s",
                (project_id,)
            )

            # 새로운 dept_ids insert
            for dept_id in dept_ids:
                cur.execute(
                    "INSERT INTO project_depts (project_id, dept_id) VALUES (%s, %s)",
                    (project_id, dept_id)
                )

        self.db.commit()
        return True

    def list_permissions(self, project_id: int):
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT dept_id FROM project_depts WHERE project_id = %s",
                (project_id,)
            )
            rows = cur.fetchall()
            return [r["dept_id"] for r in rows]
