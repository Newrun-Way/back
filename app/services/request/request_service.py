# app/services/request/request_service.py
from app.core.db import get_connection

class RequestService:
    def __init__(self):
        pass

    def list(self, status=None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                base = """
                    SELECT 
                        r.*, 
                        u.user_name, 
                        p.project_name,
                        d.original_filename AS document_name
                    FROM requests r
                    LEFT JOIN users u ON r.requester_id = u.id
                    LEFT JOIN projects p ON r.project_id = p.project_id
                    LEFT JOIN documents d ON r.target_document_id = d.id
                """

                if status:
                    sql = base + " WHERE r.status=%s ORDER BY r.id DESC"
                    cur.execute(sql, (status,))
                else:
                    sql = base + " ORDER BY r.id DESC"
                    cur.execute(sql)

                return cur.fetchall()
        finally:
            db.close()

    def create(self, requester_id, project_id, request_type, target_document_id, content):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    INSERT INTO requests
                        (requester_id, project_id, request_type,
                         target_document_id, content, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'PENDING', NOW(), NOW())
                """
                cur.execute(sql, (
                    requester_id, project_id, request_type,
                    target_document_id, content
                ))
                db.commit()
                return cur.lastrowid
        finally:
            db.close()

    def get(self, request_id):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM requests WHERE id=%s", (request_id,))
                return cur.fetchone()
        finally:
            db.close()

    def update_status(self, request_id, status, rejection_reason=None, error_message=None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    UPDATE requests
                    SET status=%s,
                        rejection_reason=%s,
                        error_message=%s,
                        updated_at=NOW()
                    WHERE id=%s
                """
                cur.execute(sql, (status, rejection_reason, error_message, request_id))
                db.commit()
        finally:
            db.close()

    def save_task_id(self, request_id, task_id):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE requests
                    SET celery_task_id=%s, updated_at=NOW()
                    WHERE id=%s
                """, (task_id, request_id))
                db.commit()
        finally:
            db.close()

    def save_error(self, request_id, message):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE requests
                    SET status='FAILED', error_message=%s, updated_at=NOW()
                    WHERE id=%s
                """, (message, request_id))
                db.commit()
        finally:
            db.close()

    def list_by_dept(self, dept_id: int, status: str | None = None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    SELECT 
                        r.*, 
                        u.user_name,
                        p.project_name,
                        d.original_filename AS document_name
                    FROM requests r
                    JOIN users u ON r.requester_id = u.id
                    LEFT JOIN projects p ON r.project_id = p.project_id
                    LEFT JOIN documents d ON r.target_document_id = d.id
                    WHERE u.dept_id = %s
                """
                params = [dept_id]

                if status:
                    sql += " AND r.status = %s"
                    params.append(status)

                sql += " ORDER BY r.created_at DESC"

                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            db.close()

    def list_by_project(self, project_id: int, status: str | None = None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                sql = """
                    SELECT 
                        r.*, 
                        u.user_name,
                        p.project_name,
                        d.original_filename AS document_name
                    FROM requests r
                    JOIN users u ON r.requester_id = u.id
                    LEFT JOIN projects p ON r.project_id = p.project_id
                    LEFT JOIN documents d ON r.target_document_id = d.id
                    WHERE r.project_id = %s
                """
                params = [project_id]

                if status:
                    sql += " AND r.status = %s"
                    params.append(status)

                sql += " ORDER BY r.created_at DESC"

                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            db.close()
