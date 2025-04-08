from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import db

class Company(db.Model):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False)
    duns = Column(String(20), unique=True, nullable=False)
    active = Column(Boolean, default=True, nullable=True)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Relaciones diferenciadas por foreign_keys
    user = relationship("User", foreign_keys=[user_id], backref="companies")
    creator = relationship("User", foreign_keys=[created_by], backref="created_companies")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Company {self.company_name} - DUNS: {self.duns}>"

