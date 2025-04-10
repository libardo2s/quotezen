from sqlalchemy import Column, Integer, String, DateTime, Enum, Index, Boolean
from datetime import datetime
from app.database import db

class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(200), nullable=True)
    active = Column(Boolean, default=True, nullable=True)
    deleted = Column(Boolean, default=False, nullable=True)

    # Role field with Enum restriction (only 'Admin', 'Shipper', or 'Carrier')
    role = Column(
        Enum(
            'Admin', 
            'CompanyShipper', 
            'Shipper', 
            'Carrier', 
            'CarrierAdmin',
            'ShipperAdmin', 
            name='user_roles'
        ), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email} - {self.role.value}>"

Index('idx_users_email', User.email)