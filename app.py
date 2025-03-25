from flask import Flask
from config import Config
from database import db
from flask_migrate import Migrate

# Import Models
from models.company import Company
from models.user import User
from models.shipper import Shipper
#from models.carrier import Carrier
#from models.quote import Quote
#from models.lane import Lane

# Import Blueprint for Routes
from routes import app_routes

# Initialize Flask App
app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

# Initialize Migrations (AFTER defining app & db)
migrate = Migrate(app, db)

# Register Blueprints
app.register_blueprint(app_routes)

# Create tables if they don't exist
with app.app_context():
    db.create_all()
    #existing_user = User.query.filter_by(email='libardoii@hotmail.com').first()
    '''
    if not existing_user:
        new_user = User(
            first_name='Libardo',
            last_name='Cuello',
            email='libardoii@hotmail.com',
            phone='1234567890',
            address='123 Test Street',
            role='Admin'  # or 'Carrier', 'Shipper', etc.
        )
        db.session.add(new_user)
        db.session.commit()
        print("User created successfully.")
    else:
        print("User already exists.")
    '''

if __name__ == '__main__':
    app.run(debug=True)
