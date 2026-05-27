import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from jose import jwt, JWTError

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SECRET = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
_ALGO = "HS256"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    if req.username != os.getenv("ADMIN_USERNAME", "admin") or \
       req.password != os.getenv("ADMIN_PASSWORD", "password"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {"sub": req.username, "exp": datetime.utcnow() + timedelta(hours=24)},
        _SECRET, algorithm=_ALGO,
    )
    return {"token": token, "username": req.username}


def require_auth(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(authorization[7:], _SECRET, algorithms=[_ALGO])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_api_key(x_api_key: str = Header(None)):
    expected = os.getenv("INGEST_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
