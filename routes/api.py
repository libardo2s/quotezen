from flask import jsonify
from routes import app_routes  # Import the blueprint

@app_routes.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({"status": "API is running!"})
