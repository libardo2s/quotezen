from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import db  # Import db from database.py

class Quote(db.Model):
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic Details
    mode = Column(String(50), nullable=False)  # Transport mode (e.g., Air, Ground, Ocean)
    equipment_type = Column(String(50), nullable=False)  # Type of truck/trailer
    temp_controlled = Column(Boolean, default=False)  # Whether temperature control is required
    rate_type = Column(String(50), nullable=False)  # Type of rate (e.g., Flat, Per Mile)

    # Locations
    origin = Column(String(100), nullable=False)  # City, State, Zip
    destination = Column(String(100), nullable=False)  # City, State, Zip

    # Shipment Information
    pickup_date = Column(DateTime, nullable=False)  # When the shipment is picked up
    delivery_date = Column(DateTime, nullable=False)  # When the shipment is delivered

    commodity = Column(String(100), nullable=False)  # Type of goods
    weight = Column(Float, nullable=False)  # Weight of shipment
    declared_value = Column(Float, nullable=True)  # Declared monetary value

    # Additional Details
    additional_stops = Column(Integer, default=0)  # Number of additional stops
    lorem_ipsum = Column(Text, nullable=True)  # Placeholder for future data if needed
    accessorials = Column(Text, nullable=True)  # Extra services like straps, pallet exchange
    comments = Column(Text, nullable=True)  # Additional comments or notes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
