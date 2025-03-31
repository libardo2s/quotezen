from flask import Flask
from config import Config
from database import db
from models.user import User


# Initialize Flask App
app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

with app.app_context():
    existing_user = User.query.filter_by(email='kevin@kanalyticstech.com').first()

    if not existing_user:
        new_user = User(
            first_name='Kevin',
            last_name='Rosales',
            email='kevin@kanalyticstech.com',
            phone='1234567890',
            address='123 Test Street',
            role='Admin'  # or 'Carrier', 'Shipper', etc.
        )
        db.session.add(new_user)
        db.session.commit()
        print("User created successfully.")
    else:
        print("User already exists.")
