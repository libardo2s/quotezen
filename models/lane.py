from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import db  # Import db from database.py

class Lane(db.Model):
    __tablename__ = 'lanes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    nickname = Column(String(100), nullable=True)  # Optional nickname for the lane
    origin = Column(String(100), nullable=False)  # City, State, Zip
    destination = Column(String(100), nullable=False)  # City, State, Zip
    
    equipment_type = Column(String(50), nullable=False)  # Type of equipment (e.g., Reefer, Dry Van)
    temp = Column(Float, nullable=True)  # Temperature setting (if applicable)
    rate_type = Column(String(50), nullable=False)  # All-in, Per Mile, etc.
    
    number_of_carriers = Column(Integer, default=0)  # Number of carriers assigned to this lane
    last_sent = Column(DateTime, default=datetime.utcnow)  # Last time the quote request was sent

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Carrier
    #carriers = relationship("Carrier", secondary=lane_carriers, back_populates="lanes")
