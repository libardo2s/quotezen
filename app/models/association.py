from sqlalchemy import Table, Column, Integer, ForeignKey, Numeric, Text
from app.database import db

carrier_shipper = Table(
    'carrier_shipper',
    db.Model.metadata,
    Column('carrier_id', Integer, ForeignKey('carriers.id'), primary_key=True),
    Column('shipper_id', Integer, ForeignKey('shippers.id'), primary_key=True)
)

quote_carrier = Table(
    'quote_carrier',
    db.Model.metadata,
    Column('quote_id', Integer, ForeignKey('quotes.id'), primary_key=True),
    Column('carrier_id', Integer, ForeignKey('carriers.id'), primary_key=True),
    Column('rate', Numeric(10, 2), nullable=True),
    Column('comment', Text, nullable=True) 
)