from flask import jsonify, request, session
from routes import app_routes
from config import Config
from botocore.exceptions import ClientError
import boto3


@app_routes.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({"status": "API is running!"})


@app_routes.route("/api/signin", methods=["POST"])
def api_sign_in():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return jsonify({
            "status": "error",
            "message": "Missing username or password."
        }), 400

    client = boto3.client("cognito-idp", region_name=Config.COGNITO_REGION)

    try:
        response = client.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            },
            ClientId=Config.CLIENT_ID
        )

        tokens = response.get("AuthenticationResult", {})
        session["access_token"] = tokens.get("AccessToken")
        session["id_token"] = tokens.get("IdToken")
        session["refresh_token"] = tokens.get("RefreshToken")

        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "redirect_url": "/dashboard"
        })

    except client.exceptions.NotAuthorizedException:
        return jsonify({
            "status": "error",
            "message": "Invalid username or password."
        }), 401
    except client.exceptions.UserNotFoundException:
        return jsonify({
            "status": "error",
            "message": "User not found."
        }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500


@app_routes.route("/api/forgot_password", methods=["POST"])
def api_forgot_password():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({'status': 'error', 'message': 'Email is required'}), 400

    client = boto3.client("cognito-idp", region_name=Config.COGNITO_REGION)

    try:
        client.forgot_password(ClientId=Config.CLIENT_ID, Username=username)
        return jsonify({'status': 'success', 'message': 'A reset code was sent to your email'}), 200
    except client.exceptions.UserNotFoundException:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    except client.exceptions.LimitExceededException:
        return jsonify({'status': 'error', 'message': 'Too many reset requests. Try again later.'}), 429
    except client.exceptions.CodeMismatchException:
        return jsonify({'status': 'error', 'message': 'Invalid verification code'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
