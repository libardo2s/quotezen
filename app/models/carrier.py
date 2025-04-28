from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from .association import carrier_shipper, quote_carrier
from app.database import db

class Carrier(db.Model):
    __tablename__ = 'carriers'
    __table_args__ = (
        Index('idx_carrier_name', 'carrier_name'),
        Index('idx_carrier_primary_user', 'primary_user_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    carrier_name = Column(String(100), nullable=False)
    authority = Column(String(50), nullable=True)
    scac = Column(String(20), unique=True, nullable=True)
    mc_number = Column(String(50), unique=True, nullable=True)
    active = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign keys to User
    primary_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Relationships
    users = relationship(
        "User", 
        back_populates="carrier",
        foreign_keys="[User.carrier_id]"
    )
    
    primary_user = relationship(
        "User", 
        foreign_keys=[primary_user_id],
        post_update=True  # Important for circular reference
    )
    
    created_by_user = relationship(
        "User", 
        foreign_keys=[created_by]
    )

    # Many-to-many relationships
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