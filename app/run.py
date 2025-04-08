from flask import Flask
from config import Config
from database import db
from flask_migrate import Migrate

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


if __name__ == '__main__':
    app.run(debug=True)
