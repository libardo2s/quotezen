from flask import Blueprint

# Initialize a blueprint for routes
app_routes = Blueprint("app_routes", __name__)

# Import individual route modules to register them
from app.routes.routes import *
from app.routes.api import *
