from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .association import carrier_shipper
from app.database import db  # Import db from database.py
from .association import quote_carrier


class Carrier(db.Model):
    """
    This is the carrier model with a one-to-many relationship to users
    (1 carrier can have many users)
    """
    __tablename__ = 'carriers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    carrier_name = Column(String(100), nullable=False)
    authority = Column(String(50), nullable=True)
    scac = Column(String(20), unique=True, nullable=True)
    mc_number = Column(String(50), unique=True, nullable=True)
    active = Column(Boolean, default=True, nullable=True)
    deleted = Column(Boolean, default=False, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Changed from user_id to primary_user_id to indicate this is just one of many users
    primary_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Relationships
    # Changed to represent many users for this carrier
    users = relationship("User", backref="carrier")
    
    # Relationship to the primary user
    primary_user = relationship("User", foreign_keys=[primary_user_id])
    
    created_by_user = relationship("User", backref="carrier_creator", foreign_keys=[created_by])

    shippers = relationship(
        "Shipper",
        secondary=carrier_shipper,
        back_populates="carriers"
    )

    quotes = relationship(
        'Quote',
        secondary=quote_carrier,
        back_populates='carriers'
    )

    def __repr__(self):
        return f"<Carrier: {self.carrier_name} (ID: {self.id})>"