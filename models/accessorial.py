from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from database import db  # Import db from database.py

class Accessorial(db.Model):
    __tablename__ = 'accessorials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)