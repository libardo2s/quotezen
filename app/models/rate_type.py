from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from app.database import db  # Import db from database.py

class RateType(db.Model):
    __tablename__ = 'rate_types'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    