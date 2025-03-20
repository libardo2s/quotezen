# models/associations.py
from sqlalchemy import Table, Column, Integer, ForeignKey
from database import db  # Import db instance

# Many-to-Many relationship table between Lane and Carrier
lane_carriers = Table(
    'lane_carriers',
    db.metadata,  # Ensure it's part of the correct metadata
    Column('lane_id', Integer, ForeignKey('lanes.id'), primary_key=True),
    Column('carrier_id', Integer, ForeignKey('carriers.id'), primary_key=True)
)
