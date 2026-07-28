from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    try:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS drive_connections (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) DEFAULT 'Google Drive',
                credentials_json JSON NOT NULL,
                folder_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                last_synced TIMESTAMP,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
            )
        """))
        conn.commit()
        print('Table created')
    except Exception as e:
        print('Error:', e)
