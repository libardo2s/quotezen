from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import db  # Import db from database.py
from sqlalchemy.dialects.postgresql import JSON
from .association import quote_carrier

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
    temp = Column(String(100), nullable=True, default='')

    # Additional Details
    additional_stops = Column(JSON, nullable=True) 
    accessorials = Column(Text, nullable=True)  # Extra services like straps, pallet exchange
    comments = Column(Text, nullable=True)  # Additional comments or notes

    open_unit = Column(String(50), nullable=True)
    open_value = Column(Float, nullable=True)

    carriers = relationship('Carrier', secondary=quote_carrier, back_populates='quotes')

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shipper_id = Column(Integer, ForeignKey("shippers.id"), nullable=False)
    shipper = relationship("Shipper", backref="quotes")
