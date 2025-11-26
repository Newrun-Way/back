# app/services/document/document_service.py
from app.core.db import get_connection
from datetime import datetime

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

    def create(
            self,
            doc_id,
            original_filename,
            user_id,
            dept_id,
            project_id,
            category,
            file_type,
            total_size
    ):
        """
        문서 메타데이터 저장
        """
        with self.db.cursor() as cur:
            sql = """
               INSERT INTO documents (
                   external_doc_id,
                   original_filename,
                   user_id,
                   dept_id,
                   project_id,
                   category,
                   file_type,
                   total_size,
                   upload_date
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               """

            params = (
                doc_id,
                original_filename,
                user_id,
                dept_id,
                project_id,
                category,
                file_type,
                total_size,
                datetime.now()
            )

            cur.execute(sql, params)
            self.db.commit()

        # DB에 방금 저장된 문서 정보 반환
        return self.get(doc_id)