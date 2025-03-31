from sqlalchemy import Column, Integer, String
from database import db
from sqlalchemy.orm import relationship
from models.lane import lane_accessorials


class Accessorial(db.Model):
    __tablename__ = 'accessorials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)

    lanes = relationship(
        "Lane",
        secondary=lane_accessorials,
        back_populates="accessorials"
    )
