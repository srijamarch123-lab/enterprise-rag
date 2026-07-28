# Add DriveConnection model to models.py
content = open('backend/app/models.py', 'r', encoding='utf-8').read()

drive_model = '''

class DriveConnection(Base):
    __tablename__ = "drive_connections"
    __table_args__ = {"extend_existing": True}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="Google Drive")
    credentials_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    folder_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
'''

if 'DriveConnection' not in content:
    content = content.rstrip() + drive_model
    open('backend/app/models.py', 'w', encoding='utf-8').write(content)
    print('DriveConnection model added')
else:
    print('Already exists')
