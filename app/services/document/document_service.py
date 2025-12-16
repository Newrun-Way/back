# app/services/document/document_service.py
from app.core.db import get_connection
from datetime import datetime
from typing import List

class DocumentService:
    def __init__(self):
        pass

    def list_all(self):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM documents ORDER BY id DESC")
                return cur.fetchall()
        finally:
            db.close()

    def list(self, dept_id=None, project_id=None):
        db = get_connection()
        try:
            with db.cursor() as cur:
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
        finally:
            db.close()

    def list_by_status(self, status: str):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT * FROM documents
                    WHERE status=%s
                    ORDER BY updated_at DESC
                """, (status,))
                return cur.fetchall()
        finally:
            db.close()

    def get(self, doc_id):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT * FROM documents WHERE external_doc_id = %s",
                    (doc_id,)
                )
                return cur.fetchone()
        finally:
            db.close()

    def get_by_id(self, row_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE id=%s", (row_id,))
                return cur.fetchone()
        finally:
            db.close()

    def get_by_external_doc_id(self, external_doc_id: str):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT *
                    FROM documents
                    WHERE external_doc_id = %s
                      AND deleted_at IS NULL
                """, (external_doc_id,))
                return cur.fetchone()
        finally:
            db.close()

    def get_titles_by_ids(self, doc_ids: List[int]):
        if not doc_ids:
            return []

        db = get_connection()
        try:
            with db.cursor() as cur:
                placeholders = ",".join(["%s"] * len(doc_ids))
                sql = f"""
                    SELECT id, original_filename
                    FROM documents
                    WHERE id IN ({placeholders})
                      AND deleted_at IS NULL
                """
                cur.execute(sql, doc_ids)
                return cur.fetchall()
        finally:
            db.close()

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
        db = get_connection()
        try:
            with db.cursor() as cur:
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
                new_pk = cur.lastrowid
                db.commit()

            # 생성된 문서 조회
            created = self.get(doc_id)
            if isinstance(created, dict):
                created["id"] = new_pk
            return created
        finally:
            db.close()

    def update_status(self, external_doc_id, status):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE documents
                    SET status=%s
                    WHERE external_doc_id=%s
                """, (status, external_doc_id))
                db.commit()
        finally:
            db.close()

    def mark_deleted(self, external_doc_id):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE documents
                    SET deleted_at = NOW(), status='DELETED'
                    WHERE external_doc_id=%s
                """, (external_doc_id,))
                db.commit()
        finally:
            db.close()
