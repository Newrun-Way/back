#app/core/auth/jwt.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def _get_secret() -> str:
    return settings.JWT_SECRET_KEY


def _get_algorithm() -> str:
    return settings.JWT_ALGORITHM


def create_access_token(
    data: Dict[str, Any],
    expires_minutes: Optional[int] = None,
) -> str:
    """
    Access Token 생성
    - payload: data (ex. {"user_id": 1})
    - exp: 설정값 JWT_EXPIRE_MINUTES 기준
    """
    expire_minutes = expires_minutes or settings.JWT_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    to_encode = data.copy()
    to_encode.update(
        {
            "exp": expire,
            "type": "access",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        _get_secret(),
        algorithm=_get_algorithm(),
    )
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_days: int = 7,
) -> str:
    """
    Refresh Token 생성
    - 기본 만료: 7일
    - payload: data (ex. {"user_id": 1})
    """
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)

    to_encode = data.copy()
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        _get_secret(),
        algorithm=_get_algorithm(),
    )
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    JWT 디코드
    - 유효하지 않거나 만료된 경우 HTTPException 발생
    """
    try:
        payload = jwt.decode(
            token,
            _get_secret(),
            algorithms=[_get_algorithm()],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )


def is_refresh_token(payload: Dict[str, Any]) -> bool:
    """
    payload 기준으로 refresh 토큰인지 확인
    """
    return payload.get("type") == "refresh"
