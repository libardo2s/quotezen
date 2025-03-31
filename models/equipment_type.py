from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from database import db  # Import db from database.py

class EquipmentType(db.Model):
    __tablename__ = 'equipment_types'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)