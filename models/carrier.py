from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import db  # Import db from database.py

class Carrier(db.Model):
    __tablename__ = 'carriers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    duns = Column(String(20), unique=True, nullable=False)  # Unique D-U-N-S number
    authority = Column(String(50), nullable=True)
    scac = Column(String(20), unique=True, nullable=True)  # Standard Carrier Alpha Code
    mc_number = Column(String(50), unique=True, nullable=True)  # Motor Carrier number


   # Foreign Key linking to Carrier
    carrier_id = Column(Integer, ForeignKey('carriers.id'), nullable=False)

    # Foreign Key linking to Shipper
    shipper_id = Column(Integer, ForeignKey('shippers.id'), nullable=False)

    # Foreign Key linking to User
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    carrier = relationship("Carrier", backref="carrier_shippers")
    user = relationship("User", backref="carrier_shippers")

    def __repr__(self):
        return f"<CarrierShipper DUNS: {self.duns} | Carrier: {self.carrier.company.company_name} | Shipper: {self.shipper.company.company_name}>"