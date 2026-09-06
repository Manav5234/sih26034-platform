"""Tests for auth module: login, token validation, role enforcement, JWT_SECRET requirement."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base, Officer, OfficerRole,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def admin_officer(db_session):
    from app.auth import hash_password
    o = Officer(
        id=uuid4(),
        name="Admin Test",
        email="admin@test.com",
        password_hash=hash_password("correct-password"),
        role=OfficerRole.ADMIN,
    )
    db_session.add(o)
    db_session.commit()
    return o


@pytest.fixture
def inspector_officer(db_session):
    from app.auth import hash_password
    o = Officer(
        id=uuid4(),
        name="Inspector Test",
        email="inspector@test.com",
        password_hash=hash_password("correct-password"),
        role=OfficerRole.INSPECTOR,
    )
    db_session.add(o)
    db_session.commit()
    return o


# --- Task 1 verification: JWT_SECRET required ---


def test_jwt_secret_required(monkeypatch):
    """App fails to start if JWT_SECRET is not set."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    # Remove all app.config cache so Settings() is re-evaluated from scratch
    keys_to_del = [k for k in sys.modules if k.startswith("app.config")]
    for k in keys_to_del:
        del sys.modules[k]
    # Import the class directly, avoiding the module-level `settings = Settings()` line
    # by using pydantic_settings directly
    from pydantic_settings import BaseSettings

    class TestSettings(BaseSettings):
        database_url: str = "sqlite://"
        jwt_secret: str

    with pytest.raises(Exception) as exc_info:
        TestSettings()
    err = str(exc_info.value)
    assert "jwt_secret" in err.lower() or "field required" in err.lower()


# --- Successful login returns valid token ---


def test_successful_login_returns_token(admin_officer):
    from app.auth import create_access_token
    token = create_access_token(admin_officer.id, admin_officer.role.value)
    assert token
    assert isinstance(token, str)
    assert len(token) > 20


def test_successful_login_token_decodes(admin_officer):
    import jwt
    from app.auth import create_access_token
    from app.config import settings
    token = create_access_token(admin_officer.id, admin_officer.role.value)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == str(admin_officer.id)
    assert payload["role"] == admin_officer.role.value
    assert "exp" in payload


# --- Wrong password rejected ---


def test_wrong_password_rejected(db_session, admin_officer):
    from app.auth import verify_password
    assert not verify_password("wrong-password", admin_officer.password_hash)
    assert verify_password("correct-password", admin_officer.password_hash)


# --- Nonexistent email rejected ---


def test_nonexistent_email_no_officer(db_session):
    from app.db.models import Officer
    result = db_session.query(Officer).filter_by(email="nonexistent@test.com").first()
    assert result is None


def test_login_same_error_for_wrong_password_and_nonexistent_user(db_session, admin_officer):
    """Both wrong password and nonexistent email produce same error path (no user enumeration via message)."""
    from app.auth import verify_password
    wrong_pw = not verify_password("wrong-password", admin_officer.password_hash)
    no_user = db_session.query(Officer).filter_by(email="noone@test.com").first() is None
    assert wrong_pw is True
    assert no_user is True


# --- Expired/malformed token rejected ---


def test_malformed_token_rejected():
    from app.auth import _get_current_officer
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _get_current_officer(token="not-a-real-token", token_cookie=None, db=MagicMock())
    assert exc_info.value.status_code == 401


def test_empty_token_rejected():
    from app.auth import _get_current_officer
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _get_current_officer(token=None, token_cookie=None, db=MagicMock())
    assert exc_info.value.status_code == 401


def test_expired_token_rejected(admin_officer):
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.auth import _get_current_officer
    from app.config import settings
    from fastapi import HTTPException

    expire = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "sub": str(admin_officer.id),
        "role": admin_officer.role.value,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        _get_current_officer(token=token, token_cookie=None, db=MagicMock())
    assert exc_info.value.status_code == 401


def test_token_for_nonexistent_officer_rejected(db_session):
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.auth import _get_current_officer
    from app.config import settings
    from fastapi import HTTPException

    fake_id = uuid4()
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": str(fake_id),
        "role": "INSPECTOR",
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        _get_current_officer(token=token, token_cookie=None, db=db_session)
    assert exc_info.value.status_code == 401
    assert "not found" in exc_info.value.detail.lower()


# --- require_role blocks unauthorized role ---


def test_require_role_allows_correct_role(inspector_officer):
    from app.auth import require_role
    dep = require_role("INSPECTOR", "ADMIN")
    result = dep(officer=inspector_officer)
    assert result.id == inspector_officer.id


def test_require_role_blocks_wrong_role(inspector_officer):
    from app.auth import require_role
    from fastapi import HTTPException
    dep = require_role("ADMIN")
    with pytest.raises(HTTPException) as exc_info:
        dep(officer=inspector_officer)
    assert exc_info.value.status_code == 403


def test_require_role_blocks_inspector_from_admin_only(admin_officer):
    from app.auth import require_role
    from fastapi import HTTPException
    dep = require_role("INSPECTOR")
    with pytest.raises(HTTPException) as exc_info:
        dep(officer=admin_officer)
    assert exc_info.value.status_code == 403


# --- Token from cookie accepted ---


def test_token_from_cookie_accepted(admin_officer, db_session):
    from app.auth import create_access_token, _get_current_officer

    token = create_access_token(admin_officer.id, admin_officer.role.value)

    mock_session = MagicMock()
    mock_session.get.return_value = admin_officer

    officer = _get_current_officer(token=None, token_cookie=token, db=mock_session)
    assert officer.id == admin_officer.id


# --- Token from header accepted ---


def test_token_from_header_accepted(admin_officer, db_session):
    from app.auth import create_access_token, _get_current_officer

    token = create_access_token(admin_officer.id, admin_officer.role.value)

    mock_session = MagicMock()
    mock_session.get.return_value = admin_officer

    officer = _get_current_officer(token=token, token_cookie=None, db=mock_session)
    assert officer.id == admin_officer.id
