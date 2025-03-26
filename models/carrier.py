from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from database import db  # Import db from database.py

class Carrier(db.Model):
    __tablename__ = 'carriers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    carrier_name = Column(String(100), nullable=False)
    duns = Column(String(20), unique=True, nullable=False)
    authority = Column(String(50), nullable=True)
    scac = Column(String(20), unique=True, nullable=True)
    mc_number = Column(String(50), unique=True, nullable=True)
    active = Column(Boolean, default=True, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)


   # Relationships
    shipper = relationship("Shipper", backref="shippers")
    user = relationship("User", backref="shippers", foreign_keys=[user_id])
    created_by_user = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<CarrierShipper DUNS: {self.duns} | Carrier: {self.carrier.company.company_name} | Shipper: {self.shipper.company.company_name}>"