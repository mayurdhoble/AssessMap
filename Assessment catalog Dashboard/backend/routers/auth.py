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


def _get_users() -> dict:
    """Return {username: password} from env vars USER1..USER4 + ADMIN fallback."""
    users = {}
    for i in range(1, 5):
        u = os.getenv(f"USER{i}_USERNAME", "")
        p = os.getenv(f"USER{i}_PASSWORD", "")
        if u and p:
            users[u] = p
    admin_u = os.getenv("ADMIN_USERNAME", "admin")
    admin_p = os.getenv("ADMIN_PASSWORD", "password")
    if admin_u not in users:
        users[admin_u] = admin_p
    return users


@router.post("/login")
def login(req: LoginRequest):
    users = _get_users()
    if users.get(req.username) != req.password:
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
