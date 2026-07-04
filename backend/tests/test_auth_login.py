from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db_module
from app.database import Base
from app.models import User, UserRole
from app.routes.auth import LoginRequest, login
from app.services.auth import hash_password


class DummyRequest:
    client = None


def test_login_succeeds_when_request_has_no_client(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session_local)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    user = User(
        email="test@example.com",
        hashed_password=hash_password("correct-password"),
        full_name="Test User",
        role=UserRole.employee,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        result = login(
            LoginRequest(email="test@example.com", password="correct-password"),
            Response(),
            DummyRequest(),
            db,
        )

        assert result["message"] == "Logged in"
        assert result["role"] == UserRole.employee
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
