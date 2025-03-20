from flask import jsonify
from routes import app_routes  # Import the blueprint

@app_routes.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the Flask API!"})
