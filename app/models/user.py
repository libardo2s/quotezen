from sqlalchemy import Column, Index, Integer, String, DateTime, Enum, Boolean, ForeignKey
from datetime import datetime
from sqlalchemy.orm import relationship
from app.database import db

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_carrier', 'carrier_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(String(200), nullable=True)
    active = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)
    
    # Foreign key to Carrier
    carrier_id = Column(Integer, ForeignKey('carriers.id'), nullable=True)
    
    # Role field
    role = Column(
        Enum(
            'Admin', 
            'CompanyShipper', 
            'Shipper', 
            'Carrier', 
            'CarrierAdmin',
            'ShipperAdmin',
            name='user_roles'
        ), nullable=False
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    carrier = relationship(
        "Carrier", 
        back_populates="users",
        foreign_keys=[carrier_id]
    )

    shipper_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<User {self.email} - {self.role}>"