from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .association import carrier_shipper
from database import db

class Shipper(db.Model):
    __tablename__ = 'shippers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True, nullable=True)

    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", backref="shippers")
    user = relationship("User", backref="shipper_user", foreign_keys=[user_id])
    created_by_user = relationship("User", backref="shipper_creator", foreign_keys=[created_by])

    carriers = relationship(
        "Carrier",
        secondary=carrier_shipper,
        back_populates="shippers"
    )

    def __repr__(self):
        return f"<Shipper {self.user.first_name} {self.user.last_name} | Company: {self.company.company_name}>"
