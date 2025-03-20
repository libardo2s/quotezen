from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import db  # Import db from database.py

class Shipper(db.Model):
    __tablename__ = 'shippers'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key linking to Company model (Shipper belongs to a company)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)

    # Foreign Key linking to User model (Shipper is managed by a user)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationship with Company
    company = relationship("Company", backref="shippers")

    # Relationship with User
    user = relationship("User", backref="shippers")

    def __repr__(self):
        return f"<Shipper {self.user.first_name} {self.user.last_name} | Company: {self.company.company_name}>"
