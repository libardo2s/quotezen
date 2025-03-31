from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from database import db

lane_accessorials = db.Table(
    'lane_accessorials',
    db.Column('lane_id', db.Integer, db.ForeignKey('lanes.id'), primary_key=True),
    db.Column('accessorial_id', db.Integer, db.ForeignKey('accessorials.id'), primary_key=True)
)


class Lane(db.Model):
    __tablename__ = 'lanes'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key to Shipper
    shipper_id = Column(Integer, ForeignKey('shippers.id'), nullable=False)

    shipper = relationship("Shipper", backref="lanes")

    # Basic Details
    nickname = Column(String(100), nullable=False)
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
    accessorials = relationship(
        "Accessorial",
        secondary=lane_accessorials,
        back_populates="lanes"
    )
    comments = Column(Text, nullable=True)  # Additional comments or notes

    leave_open_for_option = Column(String(100), nullable=False)  # Hours, Minute, Seconds
    leave_open_for_number = Column(Numeric(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
