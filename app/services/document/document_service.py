# app/services/document/document_service.py
from app.core.db import get_connection
from datetime import datetime

class DocumentService:
    def __init__(self):
        self.db = get_connection()

    def list_all(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM documents ORDER BY id DESC")
            return cur.fetchall()

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

    def list_by_status(self, status: str):
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT * FROM documents
                WHERE status=%s
                ORDER BY updated_at DESC
            """, (status,))
            return cur.fetchall()

    def get(self, doc_id):
        with self.db.cursor() as cur:
            sql = "SELECT * FROM documents WHERE external_doc_id = %s"
            cur.execute(sql, (doc_id,))
            return cur.fetchone()

    def get_by_id(self, row_id: int):
        with self.db.cursor() as cur:
            print(f"[DEBUG][SQL] SELECT * FROM documents WHERE id={row_id}")
            cur.execute("SELECT * FROM documents WHERE id=%s", (row_id,))
            result = cur.fetchone()
            print(f"[DEBUG][SQL RESULT] {result}")
            return result

    def get_by_external_doc_id(self, external_doc_id: str):
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM documents
                WHERE external_doc_id = %s
                  AND deleted_at IS NULL
            """, (external_doc_id,))
            return cur.fetchone()

    def create(
        self,
        doc_id,
        original_filename,
        user_id,
        dept_id,
        project_id,
        category,
        stored_path,
        file_ext,
        version,
        status="PENDING",
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
                version,
                upload_date,
                stored_path,
                file_ext,
                status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """

            params = (
                doc_id,
                original_filename,
                user_id,
                dept_id,
                project_id,
                category,
                version,
                datetime.now(),
                stored_path,
                file_ext,
                status,
            )

            cur.execute(sql, params)
            new_pk_id = cur.lastrowid
            print(f"[DEBUG][SQL1] {new_pk_id}")
            self.db.commit()
        created_doc = self.get(doc_id)
        print(f"[DEBUG][SQL2] {created_doc}")
        if isinstance(created_doc, dict):
            created_doc['id'] = new_pk_id
        print(f"[DEBUG][SQL3] {created_doc}")
        return created_doc


    def update_status(self, external_doc_id, status):
        with self.db.cursor() as cur:
            sql = """
                UPDATE documents
                SET status = %s
                WHERE external_doc_id = %s
            """
            cur.execute(sql, (status, external_doc_id))
            self.db.commit()

    def mark_deleted(self, doc_id):
        with self.db.cursor() as cur:
            sql = """
            UPDATE documents
            SET deleted_at = NOW(), status='DELETED'
            WHERE external_doc_id=%s
            """
            cur.execute(sql, (doc_id,))
            self.db.commit()

    # def get_latest_pending_for_user_project(self, user_id: int, project_id: int):
    #     """
    #     특정 사용자 + 프로젝트 기준으로
    #     가장 최근에 업로드된 PENDING 문서를 한 건 가져온다.
    #     (CREATE 요청에서 target_document_id 생략 시 자동 매칭용)
    #     """
    #     with self.db.cursor() as cur:
    #         sql = """
    #         SELECT *
    #         FROM documents
    #         WHERE user_id = %s
    #           AND project_id = %s
    #           AND deleted_at IS NULL
    #           AND status = 'PENDING'
    #         ORDER BY created_at DESC
    #         LIMIT 1
    #         """
    #         cur.execute(sql, (user_id, project_id))
    #         return cur.fetchone()
