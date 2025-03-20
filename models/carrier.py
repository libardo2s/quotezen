from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import db  # Import db from database.py
from models.associations import lane_carriers  # Import the Many-to-Many table

class Carrier(db.Model):
    __tablename__ = 'carriers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)  # ForeignKey to Company
    company_name = Column(String(100), nullable=False)
    authority = Column(String(50), nullable=True)
    scac = Column(String(20), unique=True, nullable=True)  # Standard Carrier Alpha Code
    mc_number = Column(String(50), unique=True, nullable=True)  # Motor Carrier number

    contact_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    contact_email = Column(String(100), unique=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Company
    company = relationship("Company", back_populates="carriers")

    # Relationship with Lane
    lanes = relationship("Lane", secondary=lane_carriers, back_populates="carriers")
