#app/core/auth/jwt.py
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException

SECRET_KEY = "YOUR_SECRET_KEY"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: int = 60 * 24):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(401, "Token is invalid or expired")
