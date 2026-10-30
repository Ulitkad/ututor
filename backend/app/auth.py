import hashlib
import os
import secrets
import time
from collections import defaultdict, deque

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .database import get_db
from .models import RefreshSession, User

SECRET = os.getenv("JWT_SECRET", "")
if len(SECRET) < 32:
    raise RuntimeError("Set JWT_SECRET to a random secret of at least 32 characters.")
SECURE_COOKIES = os.getenv("COOKIE_SECURE", "false").lower() == "true"
ACCESS_SECONDS = 15 * 60
REFRESH_SECONDS = 30 * 86400
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
login_attempts = defaultdict(deque)


def rate_limit(request: Request):
    # Never trust client-supplied X-Forwarded-For. Nginx overwrites X-Real-IP.
    host = request.headers.get("x-real-ip") if os.getenv("TRUST_NGINX") == "true" else None
    host = host or request.client.host
    now = time.time()
    for key in list(login_attempts):
        if not login_attempts[key] or login_attempts[key][-1] < now - 300:
            del login_attempts[key]
    attempts = login_attempts[host]
    while attempts and attempts[0] < now - 300:
        attempts.popleft()
    if len(attempts) >= 20:
        raise HTTPException(429, "Слишком много попыток. Повторите через 5 минут.")
    attempts.append(now)


def decode(token, kind):
    try:
        data = jwt.decode(token, SECRET, algorithms=["HS256"], options={"require": ["exp", "sub", "kind", "v"]})
        if data["kind"] != kind:
            raise ValueError()
        return data
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Сессия истекла. Войдите снова.")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, "Необходима авторизация.")
    data = decode(credentials.credentials, "access")
    user = db.get(User, int(data["sub"]))
    if not user or user.token_version != data["v"]:
        raise HTTPException(401, "Сессия истекла.")
    return user


def admin(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Доступно только администратору.")
    return user


def public_user(user):
    return {"id": user.id, "username": user.username, "name": user.name, "role": user.role}


def issue_tokens(user, db, response):
    now = int(time.time())
    common = {"sub": str(user.id), "v": user.token_version, "iat": now}
    access = jwt.encode({**common, "kind": "access", "exp": now + ACCESS_SECONDS}, SECRET, algorithm="HS256")
    jti = secrets.token_urlsafe(32)
    refresh = jwt.encode({**common, "kind": "refresh", "jti": jti, "exp": now + REFRESH_SECONDS}, SECRET, algorithm="HS256")
    db.add(RefreshSession(id=hashlib.sha256(jti.encode()).hexdigest(), user_id=user.id, expires=now + REFRESH_SECONDS))
    db.query(RefreshSession).filter(RefreshSession.expires < now).delete()
    db.commit()
    response.set_cookie("refresh_token", refresh, httponly=True, secure=SECURE_COOKIES, samesite="strict", path="/api/auth", max_age=REFRESH_SECONDS)
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": access, "token_type": "bearer", "user": public_user(user)}


def refresh_user(token, db):
    if not token:
        raise HTTPException(401, "Необходима авторизация.")
    data = decode(token, "refresh")
    jti = hashlib.sha256(data.get("jti", "").encode()).hexdigest()
    session = db.get(RefreshSession, jti)
    user = db.get(User, int(data["sub"]))
    if not session or not user or session.user_id != user.id or user.token_version != data["v"]:
        raise HTTPException(401, "Сессия истекла.")
    # Delete atomically: parallel refresh calls cannot reuse a rotated token.
    count = db.query(RefreshSession).filter(RefreshSession.id == jti).delete()
    if count != 1:
        raise HTTPException(401, "Токен уже обновлён.")
    return user
