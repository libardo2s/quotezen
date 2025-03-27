from sqlalchemy import Table, Column, Integer, ForeignKey
from database import db

carrier_shipper = Table(
    'carrier_shipper',
    db.Model.metadata,
    Column('carrier_id', Integer, ForeignKey('carriers.id'), primary_key=True),
    Column('shipper_id', Integer, ForeignKey('shippers.id'), primary_key=True)
)