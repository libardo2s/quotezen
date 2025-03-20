from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import db

class Company(db.Model):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False)
    duns = Column(String(20), unique=True, nullable=False)  # D-U-N-S number should be unique

    # Foreign Key linking to User model (assuming a company has an associated user)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationship with User model
    user = relationship("User", backref="companies")

    def __repr__(self):
        return f"<Company {self.company_name} - DUNS: {self.duns}>"
