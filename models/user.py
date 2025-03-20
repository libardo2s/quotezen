from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime
from database import db  # Import db from database.py

class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    contact_phone = Column(String(20), nullable=True)

    # Role field with Enum restriction (only 'Admin', 'Shipper', or 'Carrier')
    role = Column(Enum('Admin', 'Shipper', 'Carrier', name='user_roles'), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
