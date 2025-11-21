from app.core.db import get_connection

class ProjectService:
    def __init__(self):
        self.db = get_connection()

    def list(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM projects ORDER BY id DESC")
            return cur.fetchall()

    def create(self, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (project_name, dept_id) VALUES (%s, %s)",
                (name, dept_id)
            )
            self.db.commit()
            return cur.lastrowid

    def update(self, project_id: int, name: str):
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE projects SET project_name=%s, dept_id=%s WHERE id=%s",
                (name, dept_id, project_id)
            )
            self.db.commit()
            return cur.rowcount

    def delete(self, project_id: int):
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM projects WHERE id=%s", (project_id,))
            self.db.commit()
            return cur.rowcount

    def get_by_dept_id(self, dept_id: int):
        with self.db.cursor() as cur:
            # DB의 컬럼명이 'dept_id'라고 가정하고 작성했습니다.
            sql = """
                SELECT project_id, project_name, dept_id
                FROM projects 
                WHERE dept_id = %s
            """
            cur.execute(sql, (dept_id,))
            rows = cur.fetchall()

            # 결과를 딕셔너리 리스트로 변환
            return [
                {
                    "project_id": row[0],
                    "project_name": row[1],
                    "dept_id": row[2],
                }
                for row in rows
            ]
