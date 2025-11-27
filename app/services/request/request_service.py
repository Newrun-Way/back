# app/services/request/request_service.py
from app.core.db import get_connection
from datetime import datetime

class RequestService:
    def __init__(self):
        self.db = get_connection()

    def create(self, requester_id, project_id, request_type,
               target_document_id=None, content=None):
        with self.db.cursor() as cur:
            sql = """
            INSERT INTO requests (
                requester_id, project_id, target_document_id,
                request_type, content, status, created_at
            ) VALUES (%s,%s,%s,%s,%s,'PENDING',NOW())
            """
            cur.execute(sql, (requester_id, project_id, target_document_id,
                              request_type, content))
            self.db.commit()
            return cur.lastrowid

    def get(self, req_id):
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM requests WHERE id=%s", (req_id,))
            return cur.fetchone()

    def update_status(self, req_id, status, rejection_reason=None):
        with self.db.cursor() as cur:
            sql = """
            UPDATE requests
            SET status=%s,
                rejection_reason=%s,
                updated_at=NOW()
            WHERE id=%s
            """
            cur.execute(sql, (status, rejection_reason, req_id))
            self.db.commit()
