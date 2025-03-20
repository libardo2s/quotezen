from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from database import db  # Import db from database.py

class Company(db.Model):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False, unique=True)
    duns = Column(String(20), unique=True, nullable=True)  # DUNS (Data Universal Numbering System)

    contact_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    contact_email = Column(String(100), unique=True, nullable=False)

    address = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Carrier
    carriers = db.relationship('Carrier', back_populates='company', cascade="all, delete-orphan")
