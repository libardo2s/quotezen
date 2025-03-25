import boto3
from database import db
from flask import jsonify, request, session
from routes import app_routes
from config import Config
from botocore.exceptions import ClientError
from models import User, Company
from sqlalchemy.exc import IntegrityError
from utils.token_required import token_required


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

        # Fetch user from the database
        user = User.query.filter_by(email=username).first()

        if user:
            session["user_id"] = user.id
            session["user_name"] = user.email
            session["user_role"] = user.role  # Store user role

        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "redirect_url": "/dashboard",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
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

@app_routes.route("/api/company", methods=["GET", "POST"])
#@token_required
def api_company():
    if request.method == "GET":
        companies = Company.query.all()
        return jsonify([
            {
                "id": company.id,
                "company_name": company.company_name,
                "duns": company.duns,
                "user": {
                    "first_name": company.user.first_name,
                    "phone": company.user.phone,
                    "address": company.user.address,
                    "email": company.user.email
                } if company.user else None
            }
            for company in companies
        ])

    if request.method == "POST":
        try:
            # Retrieve form data
            company_name = request.form.get("company_name")
            duns = request.form.get("duns")
            contact_name = request.form.get("contact_name")
            contact_phone = request.form.get("contact_phone")
            address = request.form.get("address")
            contact_email = request.form.get("contact_email")

            # Validate required fields
            if not all([company_name, duns, contact_name, contact_phone, address, contact_email]):
                return jsonify({"status": "error", "message": "All fields are required"}), 400

            # Create a user for the company (CompanyShipper role)
            company_user = User(
                first_name=contact_name,
                last_name="",
                email=contact_email,
                phone=contact_phone,
                address=address,
                role="CompanyShipper"
            )

            db.session.add(company_user)
            db.session.commit()

            # Create the company associated with the user
            new_company = Company(
                company_name=company_name,
                duns=duns,
                user_id=company_user.id
            )

            db.session.add(new_company)
            db.session.commit()

            # Return new table row for HTMX
            return jsonify({"status": "success", "message": "Company created"}), 200

        except IntegrityError as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    

@app_routes.route("/api/company/<int:company_id>", methods=["GET"])
# @token_required
def get_company_by_id(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"status": "error", "message": "Company not found"}), 404

    return jsonify({
        "id": company.id,
        "company_name": company.company_name,
        "duns": company.duns,
        "user": {
            "first_name": company.user.first_name,
            "phone": company.user.phone,
            "address": company.user.address,
            "email": company.user.email
        } if company.user else None
    })

@app_routes.route("/api/company/<int:company_id>", methods=["PUT"])
def update_company(company_id):
    data = request.form  # HTMX sends data as form-encoded

    company = Company.query.get(company_id)
    if not company:
        return jsonify({"status": "error", "message": "Company not found"}), 404

    # Update Company fields
    company.company_name = data.get("company_name", company.company_name)
    company.duns = data.get("duns", company.duns)

    # Update associated User fields
    user = company.user
    if user:
        user.first_name = data.get("contact_name", user.first_name)
        user.phone = data.get("contact_phone", user.phone)
        user.address = data.get("address", user.address)
        user.email = data.get("contact_email", user.email)

    try:
        db.session.commit()
        return jsonify({"status": "success", "message": "Company updated successfully!"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "DUNS number must be unique"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


'''
if request.method == "DELETE":
    company_id = request.form.get("id")  # Use form data instead of JSON for HTMX

    if not company_id:
        return jsonify({"status": "error", "message": "Company ID is required"}), 400

    company = Company.query.get(company_id)
    if not company:
        return jsonify({"status": "error", "message": "Company not found"}), 404

    try:
        db.session.delete(company)
        db.session.commit()
        return "", 204  # HTMX will remove the row automatically
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
'''