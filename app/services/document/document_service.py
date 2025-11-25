# app/services/document/document_service.py

from app.core.db import get_connection

class DocumentService:
    def __init__(self):
        self.db = get_connection()

    def list(self, dept_id=None, project_id=None):
        with self.db.cursor() as cur:
            sql = "SELECT * FROM documents WHERE deleted_at IS NULL"
            params = []

            if dept_id:
                sql += " AND dept_id = %s"
                params.append(dept_id)

            if project_id:
                sql += " AND project_id = %s"
                params.append(project_id)

            sql += " ORDER BY upload_date DESC"

            cur.execute(sql, params)
            return cur.fetchall()

    def get(self, doc_id):
        with self.db.cursor() as cur:
            sql = "SELECT * FROM documents WHERE external_doc_id = %s"
            cur.execute(sql, (doc_id,))
            return cur.fetchone()
