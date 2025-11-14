# app/core/db.py

import pymysql
import os

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "alain_user"),
        password=os.getenv("DB_PASSWORD", "2team"),
        db=os.getenv("DB_NAME", "alain"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
