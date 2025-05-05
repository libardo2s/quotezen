from flask import Flask
from app.config import Config
from app.database import db
from flask_migrate import Migrate
from datetime import datetime

# Import Blueprint for Routes
from app.routes import app_routes

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

@app.template_filter('format_date')
def format_date(value, format='%m-%d-%Y'):
    if isinstance(value, str):
        return datetime.strptime(value, '%Y-%m-%d').strftime(format)
    return value.strftime(format)


if __name__ == '__main__':
    app.run(debug=True)
