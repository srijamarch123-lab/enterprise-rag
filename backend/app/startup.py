import bcrypt
import os

def create_default_admin():
    try:
        from app.database import SessionLocal
        from app.models import User, UserRole
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.email == "admin@company.com").first()
            if not existing:
                user = User(
                    email="admin@company.com",
                    hashed_password=bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode(),
                    full_name="Admin",
                    role=UserRole.admin,
                    is_active=True,
                    token_version=0
                )
                db.add(user)
                db.commit()
                print("Default admin created: admin@company.com / admin1234")
            else:
                print("Admin already exists")
        finally:
            db.close()
    except Exception as e:
        print(f"Admin creation skipped: {e}")
