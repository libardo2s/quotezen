from sqlalchemy import Column, Integer, ForeignKey, Numeric, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import db


# models.py

class QuoteCarrierRate(db.Model):
    __tablename__ = 'quote_carrier_rate'

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    carrier_id = db.Column(db.Integer, db.ForeignKey('carriers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    carrier_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    comment = db.Column(db.Text)
    status = db.Column(db.String, default="pending")  # accepted o pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # decision_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    quote = db.relationship('Quote', backref='quote_rates')
    carrier = db.relationship('Carrier')
    user = db.relationship('User', foreign_keys=[user_id])
    carrier_admin = db.relationship('User', foreign_keys=[carrier_admin_id])

