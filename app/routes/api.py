from decimal import Decimal
import json

import boto3
from sqlalchemy import func, or_

from app.controller import create_carrier_user, create_carrier_admin
from app.database import db
from flask import jsonify, request, session, render_template
from app.routes import app_routes
from app.config import Config
from app.models import (User, Company, Shipper, Carrier, Mode, EquipmentType, RateType, Accessorial, City, Quote,
                    QuoteCarrierRate)


from app.models.association import carrier_shipper,  quote_carrier  # si lo tienes separado
from sqlalchemy.exc import IntegrityError
#from utils.token_required import token_required
from app.utils.send_email import send_email
from cryptography.fernet import Fernet
from app.config import Config
from datetime import datetime
from psycopg2.errors import UniqueViolation

from datetime import datetime
from decimal import Decimal
from app.routes import app_routes
from app.database import db
from app.models import Lane, Accessorial

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
            session["full_name"] = f"{user.first_name} {user.last_name}"
            session["user_role"] = user.role  # Store user role
        
        if user.role == "Admin":
            redirect_url = "/dashboard"
        elif user.role == "CarrierAdmin":
            redirect_url = "/carrier_pending_quotes"
        elif user.role == "CompanyShipper":
            redirect_url = "/admin_settings"
        else:
            redirect_url = "/quotes"

        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "redirect_url": redirect_url,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        })

    except client.exceptions.NotAuthorizedException as e:
        print(Config.CLIENT_ID)
        print(f"Login error: {str(e)}")
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
        creator_id = session.get("user_id")
        companies = Company.query.filter_by(active=True, created_by=creator_id)
        return jsonify([
            {
                "id": company.id,
                "company_name": company.company_name,
                "duns": company.duns,
                "active": company.active,
                "user": {
                    "first_name": company.user.first_name,
                    "phone": company.user.phone,
                    "address": company.user.address,
                    "email": company.user.email,
                    "active": company.user.active
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

            f = Fernet(Config.HASH_KEY)
            encrypted_email = f.encrypt(contact_email.encode()).decode()

            # Send the hashed email via POST
            register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"


            # Validate required fields
            if not all([company_name, duns, contact_name, contact_phone, address, contact_email]):
                return jsonify({"status": "error", "message": "All fields are required"}), 400

            # Get creator user ID from session (or use current_user.id)
            creator_id = session.get("user_id")  # Or: current_user.id

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
                user_id=company_user.id,
                created_by=creator_id
            )

            db.session.add(new_company)
            db.session.commit()

            try:

                # Render HTML email content
                html_content = render_template("email/company_welcome_email.html", register_url=register_url)
                print(html_content)

                response = send_email(
                    recipient=contact_email,
                    subject="Welcome to QuoteZen!",
                    body_text="Welcome to QuoteZen! Please complete your registration.",
                    body_html=html_content
                )
            except Exception as e:
                print(f"Email error: {str(e)}")

            # Return new table row for HTMX
            return jsonify(
                {
                    "status": "success",
                    "message": "Company created",
                    "complete_registration": register_url}
            ), 200

        except IntegrityError as e:
            db.session.rollback()
            print(e.orig)
            if isinstance(e.orig, UniqueViolation):
                # Check which constraint was violated
                if 'companies_duns_key' in str(e.orig):
                    return jsonify({
                        "status": "error",
                        "message": "A company with this DUNS number already exists"
                    }), 400
                elif 'ix_users_email' in str(e.orig):
                    return jsonify({
                        "status": "error",
                        "message": "A user with this email already exists"
                    }), 400
            return jsonify({
                "status": "error",
                "message": "Database integrity error occurred"
            }), 400

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred. Please try again later."
            }), 500

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
# @token_required
def update_company(company_id):
    data = request.form

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

@app_routes.route("/api/company/<int:company_id>", methods=["DELETE"])
def delete_company(company_id):
    company = Company.query.get(company_id)

    if not company:
        return jsonify({"status": "error", "message": "Company not found"}), 404

    try:
        # Soft delete company
        company.active = False

        # Soft delete associated user (if exists)
        if company.user:
            company.user.active = False

        shippers = Shipper.query.filter_by(company_id=company.id).all()
        for shipper in shippers:
            shipper.active = False
            if shipper.user:
                shipper.user.active = False

        db.session.commit()
        return jsonify({"status": "success", "message": "Company deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/shipper", methods=["GET", "POST"])
#@token_required
def api_shipper():
    if request.method == "GET":
        role_user = session.get("user_role")
        if role_user == 'Admin':
            shippers = Shipper.query.filter_by(deleted=False).all()
            return jsonify([
                {
                    "id": shipper.id,
                    "company_id": shipper.company_id,
                    "active": shipper.active,
                    "user": {
                        "first_name": shipper.user.first_name,
                        "last_name": shipper.user.last_name,
                        "phone": shipper.user.phone,
                        "email": shipper.user.email,
                        "active": shipper.user.active
                    } if shipper.user else None
                }
                for shipper in shippers
            ])

        user_id = session.get("user_id")
        company = Company.query.filter_by(user_id=user_id).first()
        if not company:
            return jsonify([])

        shippers = Shipper.query.filter_by(company_id=company.id).all()

        return jsonify([
            {
                "id": shipper.id,
                "company_id": shipper.company_id,
                "active": shipper.active,
                "deleted": shipper.deleted,
                "user": {
                    "first_name": shipper.user.first_name,
                    "last_name": shipper.user.last_name,
                    "phone": shipper.user.phone,
                    "email": shipper.user.email,
                    "active": shipper.user.active
                } if shipper.user else None
            }
            for shipper in shippers
        ])

    if request.method == "POST":
        # For Shipper User
        try:
            first_name = request.form.get("first_name")
            last_name = request.form.get("last_name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            user_id = session.get("user_id")

            f = Fernet(Config.HASH_KEY)
            encrypted_email = f.encrypt(email.encode()).decode()

            # Send the hashed email via POST
            register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"

            # Get company of current user
            company = Company.query.filter_by(user_id=user_id).first()
            if not company:
                return jsonify({"success": False, "message": "Company not found"}), 404

            # Create user
            new_user = User(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                role="Shipper",
                active=True
            )
            db.session.add(new_user)
            db.session.flush()

            # Create shipper
            new_shipper = Shipper(
                user_id=new_user.id,
                company_id=company.id,
                created_by=user_id,
                active=True
            )
            db.session.add(new_shipper)
            db.session.commit()

            try:
                html_content = render_template(
                    "email/shipper_welcome_email.html",
                    name=f"{first_name} {last_name}",
                    userAdminName=company.company_name,
                    link_to_create_password=register_url
                )

                print(html_content)

                response = send_email(
                    recipient=email,
                    subject="You're invited to QuoteZen!",
                    body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                    body_html=html_content
                )
            except Exception as e:
                print(f"Email error: {str(e)}")

            # Return new table row for HTMX
            return jsonify(
                {
                    "status": "success",
                    "message": "Shipper created",
                    "complete_registration": register_url
                }), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app_routes.route("/api/shipper/<int:shipper_id>", methods=["GET"])
#@token_required
def get_shipper_by_id(shipper_id):
    shipper = Shipper.query.get(shipper_id)
    if not shipper:
        return jsonify({"status": "error", "message": "Shipper not found"}), 404

    return jsonify({
        "id": shipper.id,
        "company_id": shipper.company_id,
        "active": shipper.active,
        "user": {
            "first_name": shipper.user.first_name,
            "last_name": shipper.user.last_name,
            "phone": shipper.user.phone,
            "email": shipper.user.email,
            "active": shipper.user.active
        } if shipper.user else None
    })

@app_routes.route("/api/shipper/<int:shipper_id>", methods=["PUT"])
#@token_required
def update_shipper(shipper_id):
    shipper = Shipper.query.get(shipper_id)

    if not shipper:
        return jsonify({"status": "error", "message": "Shipper not found"}), 404

    user = shipper.user

    # Obtener datos del formulario
    data = request.form

    try:
        user.first_name = data.get("first_name")
        user.last_name = data.get("last_name")
        user.email = data.get("email")
        user.phone = data.get("phone")

        db.session.commit()
        return jsonify({"status": "success", "message": "Shipper updated successfully"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "DUNS number must be unique"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Failed to update shipper: {str(e)}"
        }), 500

@app_routes.route("/api/shipper/<int:shipper_id>", methods=["DELETE"])
#@token_required
def delete_shipper(shipper_id):
    shipper = Shipper.query.get(shipper_id)

    if not shipper:
        return jsonify({"status": "error", "message": "Shipper not found"}), 404

    try:
        # Soft delete shipper
        shipper.active = False

        # Soft delete associated user (if exists)
        if shipper.user:
            shipper.user.active = False

        db.session.commit()
        return jsonify({"status": "success", "message": "Shipper deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/carrier/", methods=["GET", "POST"])
#@token_required
def api_carrier():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        carriers = Carrier.query.filter_by(deleted=False, created_by=user_id).all()
        carrier_list = [
            {
                "id": carrier.id,
                "carrier_name": carrier.carrier_name,
                "authority": carrier.authority,
                "scac": carrier.scac,
                "mc_number": carrier.mc_number,
                "active": carrier.active,
                "created_at": carrier.created_at.isoformat(),
                "updated_at": carrier.updated_at.isoformat(),
                "user": {
                    "first_name": carrier.user.first_name,
                    "last_name": carrier.user.last_name,
                    "phone": carrier.user.phone,
                    "email": carrier.user.email,
                    "active": carrier.user.active
                } if carrier.user else None
            }
            for carrier in carriers
        ]
        return jsonify(carrier_list), 200

    if request.method == "POST":
        data = request.form
        if data.get("simple_carrier") == "true":
            return create_carrier_user(data=data, user_id=user_id, db=db)
        else:
            return create_carrier_admin(data=data, user_id=user_id, db=db)

@app_routes.route("/api/carrier/<string:mc_number>", methods=["GET"])
#@token_required
def get_carrier_by_mc(mc_number):
    carrier = Carrier.query.filter_by(
        mc_number=mc_number,
        active=True,
    ).first()

    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404

    return jsonify({
        "id": carrier.id,
        "carrier_name": carrier.carrier_name,
        "authority": carrier.authority,
        "scac": carrier.scac,
        "mc_number": carrier.mc_number,
        "active": carrier.active,
        "created_at": carrier.created_at.isoformat(),
        "updated_at": carrier.updated_at.isoformat(),
        "user": {
            "first_name": carrier.user.first_name,
            "last_name": carrier.user.last_name,
            "phone": carrier.user.phone,
            "email": carrier.user.email,
            "active": carrier.user.active
        } if carrier.user else None
    })

@app_routes.route("/api/carrier/<int:carrier_id>", methods=["GET"])
#@token_required
def get_carrier_by_id(carrier_id):
    carrier = Carrier.query.get(carrier_id)

    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404

    return jsonify({
        "id": carrier.id,
        "carrier_name": carrier.carrier_name,
        "authority": carrier.authority,
        "scac": carrier.scac,
        "mc_number": carrier.mc_number,
        "active": carrier.active,
        "created_at": carrier.created_at.isoformat(),
        "updated_at": carrier.updated_at.isoformat(),
        "user": {
            "first_name": carrier.user.first_name,
            "last_name": carrier.user.last_name,
            "phone": carrier.user.phone,
            "email": carrier.user.email,
            "active": carrier.user.active
        } if carrier.user else None
    })

@app_routes.route("/api/carrier/<int:carrier_id>", methods=["PUT"])
#@token_required
def update_carrier(carrier_id):
    try:
        data = request.form
        carrier = Carrier.query.get_or_404(carrier_id)
        if request.form.get("simple_carrier") == "true":
            # Solo actualiza el usuario
            carrier.user.first_name = request.form.get("first_name")
            carrier.user.last_name = request.form.get("last_name")
            carrier.user.email = request.form.get("email")
            carrier.user.phone = request.form.get("phone")
        else:

            carrier.carrier_name = data.get("carrier_name")
            carrier.authority = data.get("authority")
            carrier.scac = data.get("scac")
            carrier.mc_number = data.get("mc_number")

            user = carrier.user
            user.first_name = data.get("contact_name")
            user.last_name = data.get("contact_name")
            user.phone = data.get("contact_phone")
            user.email = data.get("contact_email")

        db.session.commit()

        return jsonify({"status": "success", "message": "Carrier updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Update failed: {str(e)}"}), 500

@app_routes.route('/api/carrier/<int:carrier_id>', methods=['DELETE'])
#@token_required
def delete_carrier(carrier_id):
    try:
        carrier = Carrier.query.get_or_404(carrier_id)
        carrier.deleted = True  # Set active flag to False instead of deleting
        db.session.commit()

        return jsonify({"status": "success", "message": "Carrier deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Deletion failed: {str(e)}"}), 500
    
@app_routes.route('/api/carrier/<int:carrier_id>/toggle-active', methods=['PUT'])
#@token_required
def toggle_carrier_active(carrier_id):
    try:
        carrier = Carrier.query.get_or_404(carrier_id)
        carrier.active = not carrier.active

        # Si desactivamos este carrier, también desactivamos todos los carriers creados por él
        if not carrier.active:
            created_carriers = Carrier.query.filter_by(created_by=carrier.user.id).all()
            for c in created_carriers:
                c.active = False
                c.user.active = False

        db.session.commit()
        status = "activated" if carrier.active else "deactivated"
        return jsonify({"status": "success", "message": f"Carrier {status} successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Toggle failed: {str(e)}"}), 500

def get_all_created_user_ids(user_id):
    """
    Recursively collect all user IDs (carriers) created by the given user.
    """
    visited = set()
    queue = [user_id]

    while queue:
        current_user_id = queue.pop()
        if current_user_id in visited:
            continue
        visited.add(current_user_id)

        # Fetch carriers where created_by matches this user ID
        carriers_created = Carrier.query.filter_by(created_by=current_user_id, active=True).all()

        for carrier in carriers_created:
            if carrier.user_id:  # If carrier has a user
                queue.append(carrier.user_id)

    return visited

@app_routes.route("/api/carrier_quotes/", methods=["GET"])
def carrier_quotes():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    carriers = (
        Carrier.query
        .join(User, Carrier.user_id == User.id)
        .filter(
            Carrier.active.is_(True),
            Carrier.created_by == user_id,
            User.role == 'CarrierAdmin'
        )
        .all()
    )

    carrier_list = [
        {
            "id": carrier.id,
            "carrier_name": carrier.carrier_name,
            "authority": carrier.authority,
            "scac": carrier.scac,
            "mc_number": carrier.mc_number,
            "active": carrier.active,
            "created_at": carrier.created_at.isoformat(),
            "updated_at": carrier.updated_at.isoformat(),
            "user": {
                "first_name": carrier.user.first_name,
                "last_name": carrier.user.last_name,
                "phone": carrier.user.phone,
                "email": carrier.user.email,
                "active": carrier.user.active
            } if carrier.user else None
        }
        for carrier in carriers
    ]

    return jsonify(carrier_list), 200

@app_routes.route("/api/modes", methods=["GET"])
def api_modes():
    modes = Mode.query.all()
    mode_list = [
        {
            "id": mode.id,
            "name": mode.name,
        }
        for mode in modes
    ]
    return jsonify(mode_list), 200

@app_routes.route("/api/equipment_types", methods=["GET"])
def api_equipment_types():
    equipment_types = EquipmentType.query.all()
    equipment_list = [
        {
            "id": equipment.id,
            "name": equipment.name,
        }
        for equipment in equipment_types
    ]
    return jsonify(equipment_list), 200

@app_routes.route("/api/rate_types", methods=["GET"])
def api_rate_types():
    rate_types = RateType.query.all()
    rate_list = [
        {
            "id": rate.id,
            "name": rate.name,
        }
        for rate in rate_types
    ]
    return jsonify(rate_list), 200

@app_routes.route("/api/accessorials", methods=["GET"])
def api_accessorials():
    accessorials = Accessorial.query.all()
    accessorial_list = [
        {
            "id": accessorial.id,
            "name": accessorial.name,
        }
        for accessorial in accessorials
    ]
    return jsonify(accessorial_list), 200

@app_routes.route("/api/autocomplete-location", methods=["GET"])
def autocomplete_location():
    term = request.args.get("q", "").strip().lower()
    if not term:
        return jsonify([])

    # Si el término es numérico, buscar solo por código postal
    if term.isdigit():
        query = City.query.filter(City.postal_code.ilike(f"%{term}%"))
        results = query.limit(10).all()
        
        response = [
            {
                "label": f"{city.city_name}, {city.province_abbr} {city.postal_code} ({city.country_name})",
                "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}"
            }
            for city in results
        ]
        return jsonify(response)

    # Primero intentamos buscar el término completo en ciudad
    query_full = City.query.filter(City.city_name.ilike(f"%{term}%"))
    results_full = query_full.limit(10).all()

    if results_full:
        # Si encontramos resultados con el término completo, los devolvemos
        response = [
            {
                "label": f"{city.city_name}, {city.province_abbr} {city.postal_code} ({city.country_name})",
                "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}"
            }
            for city in results_full
        ]
        return jsonify(response)

    # Si no hay resultados con el término completo, procedemos con el split
    search_terms = [t.strip() for t in term.replace(',', ' ').split() if t.strip()]

    # Construir la consulta base
    query = City.query

    # Si hay múltiples términos, el primero busca en ciudad y los demás en provincia
    if len(search_terms) > 1:
        city_term = search_terms[0]
        province_terms = search_terms[1:]
        
        query = query.filter(City.city_name.ilike(f"%{city_term}%"))
        
        # Filtrar por cada término de provincia (búsqueda flexible)
        province_filters = []
        for term in province_terms:
            province_filters.append(City.province_name.ilike(f"%{term}%"))
            province_filters.append(City.province_abbr.ilike(f"%{term}%"))
        
        query = query.filter(db.or_(*province_filters))
    else:
        # Búsqueda simple en todos los campos relevantes
        single_term = search_terms[0]
        query = query.filter(
            db.or_(
                City.city_name.ilike(f"%{single_term}%"),
                City.province_name.ilike(f"%{single_term}%"),
                City.province_abbr.ilike(f"%{single_term}%"),
                City.postal_code.ilike(f"%{single_term}%")
            )
        )

    results = query.limit(10).all()

    response = [
        {
            "label": f"{city.city_name}, {city.province_abbr} {city.postal_code} ({city.country_name})",
            "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}"
        }
        for city in results
    ]

    return jsonify(response)


def send_emails_to_carrier_company_and_users(selected_carriers, quote_id, shipper_name):
    """
    Sending email for carrier companies
    """
    try:
        f = Fernet(Config.HASH_KEY)
        encrypted_id = f.encrypt(str(quote_id).encode()).decode()
        # Send the hashed email via POST
        quote_url = f"{Config.DOMAIN_URL}/carrier_pending_quotes/{encrypted_id}"
        for carrier in selected_carriers:
            if carrier.user.email:
                html_content = render_template(
                    "email/quote.html",
                    quote_url=quote_url,
                    current_year=datetime.now().year,
                    carrier_name=carrier.carrier_name,
                    shipper_name=shipper_name,
                )

                response = send_email(
                    recipient=carrier.user.email,
                    subject="New Quote Available - Urgent",
                    body_text="You have a new quote available in QuoteZen.",
                    body_html=html_content
                )
                print(f"Email sent to {carrier.user.email}: {response}")
            
            creator_carriers = Carrier.query.filter_by(created_by=carrier.user.id).all()
            for creator_carrier in creator_carriers:                
                    html_content = render_template(
                        "email/quote.html",
                        quote_url=quote_url,
                        current_year=datetime.now().year,
                        carrier_name=creator_carrier.carrier_name,
                        shipper_name=shipper_name,
                    )

                    response = send_email(
                        recipient=creator_carrier.user.email,
                        subject="New Quote Available - Urgent",
                        body_text="You have a new quote available in QuoteZen.",
                        body_html=html_content
                    )
                    print(f"Email sent to creator's other carrier {creator_carrier.user.email}: {response}")
    except Exception as e:
        print(f"Email error: {str(e)}")


@app_routes.route("/api/quote", methods=["GET", "POST"])
def api_quote():
    if request.method == "GET":
        pass

    if request.method == "POST":
        try:
            form = request.form
            user_id = session.get("user_id")

            shipper = Shipper.query.filter_by(user_id=user_id).first()
            if not shipper:
                return jsonify({"status": "error", "message": "User is not a shipper"}), 403

            carrier_ids = form.getlist("carrier_ids[]") 

            if not carrier_ids:
                return jsonify({"status": "error", "message": "No carriers selected"}), 400

            stops_json = form.get("stops", "[]")  # Obtiene el string JSON
            additional_stops = json.loads(stops_json)  # Convierte a lista/dict
            print("Parsed stops:", additional_stops) 


            # Query selected company carriers
            selected_carriers = Carrier.query.filter(Carrier.id.in_(carrier_ids)).all()
            carriers_of_company_carrier = Carrier.query.filter(Carrier.created_by.in_(carrier_ids)).all()

            quote = Quote(
                mode=form.get("mode"),
                equipment_type=form.get("equipment_type"),
                rate_type=form.get("rate_type"),
                temp_controlled=False,
                origin=form.get("origin"),
                destination=form.get("destination"),
                pickup_date=datetime.strptime(form.get("pickup_date"), "%Y-%m-%d") if form.get("pickup_date") else None,
                delivery_date=datetime.strptime(form.get("delivery_date"), "%Y-%m-%d") if form.get("delivery_date") else None,
                commodity=form.get("commodity"),
                weight=float(form.get("weight") or 0),
                declared_value=float(form.get("declared_value") or 0),
                accessorials=",".join(form.getlist("accessorials[]")),
                comments=form.get("comments"),
                additional_stops=additional_stops,
                carriers=selected_carriers,
                open_unit=form.get("leave_open_unit"),
                open_value=form.get("leave_open_value"),
                shipper_id=shipper.id  # 👈 aquí se asigna el shipper
            )

            db.session.add(quote)
            db.session.commit()

            
            send_emails_to_carrier_company_and_users(
                selected_carriers=selected_carriers + carriers_of_company_carrier,
                quote_id=quote.id,
                shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
            )
            
            return jsonify({"status": "success", "quote_id": quote.id})

        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
        

@app_routes.route("/api/quote/<int:quote_id>", methods=["GET"])
def get_quote_by_id(quote_id):
    quote = Quote.query.get(quote_id)
    if not quote:
        return jsonify({"status": "error", "message": "Quote not found"}), 404

    # Convert the additional_stops JSON string to a Python object
    try:
        additional_stops = json.loads(quote.additional_stops) if quote.additional_stops else []
    except json.JSONDecodeError:
        additional_stops = []

    return jsonify({
        "id": quote.id,
        "mode": quote.mode,
        "equipment_type": quote.equipment_type,
        "rate_type": quote.rate_type,
        "temp_controlled": quote.temp_controlled,
        "origin": quote.origin,
        "destination": quote.destination,
        "pickup_date": quote.pickup_date.isoformat() if quote.pickup_date else None,
        "delivery_date": quote.delivery_date.isoformat() if quote.delivery_date else None,
        "commodity": quote.commodity,
        "weight": float(quote.weight) if quote.weight else 0.0,
        "declared_value": float(quote.declared_value) if quote.declared_value else 0.0,
        "accessorials": [a.strip() for a in (quote.accessorials or "").split(",")],
        "comments": quote.comments,
        "additional_stops": additional_stops
    }), 200


@app_routes.route("/api/update_rate", methods=["POST"])
def api_update_rate():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        quote_id = request.form.get("quote_id", type=int)
        carrier_id = request.form.get("carrier_id", type=int)
        rate_str = request.form.get("rate")
        comment = request.form.get("comment", "")

        if not all([quote_id, carrier_id, rate_str]):
            return jsonify({"status": "error", "message": "Missing data"}), 400

        try:
            rate = Decimal(rate_str)
        except Exception:
            return jsonify({"status": "error", "message": "Invalid rate format"}), 400

        carrier_admin = Carrier.query.get(carrier_id)

        # Guardar historial en QuoteCarrierRate (auditoría)
        quote_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote_id,
            carrier_id=carrier_id
        ).first()

        if quote_rate:
            quote_rate.rate = rate
            quote_rate.comment = comment
            quote_rate.created_at = datetime.utcnow()
        else:
            quote_rate = QuoteCarrierRate(
                quote_id=quote_id,
                carrier_id=carrier_id,
                user_id=user_id,
                carrier_admin_id=carrier_admin.user.id,
                rate=rate,
                comment=comment,
                created_at=datetime.utcnow()
            )
            db.session.add(quote_rate)

        # También actualizamos la tabla quote_carrier
        
        db.session.execute(
            quote_carrier.update()
            .where(quote_carrier.c.quote_id == quote_id)
            .where(quote_carrier.c.carrier_id == carrier_id)
            .values(rate=rate, comment=comment)
        )

        db.session.commit()
        return "", 204
    except Exception as e:
        print("[ERROR]", str(e))
        return jsonify({"status": "error", "message": "Internal error"}), 500


@app_routes.route("/api/quote/decision", methods=["POST"])
def quote_decision():
    try:
        data = request.get_json()
        quote_id = data.get("quote_id")
        carrier_admin_id = data.get("carrier_admin_id")
        rate = data.get("rate")
        decision = data.get("decision")  # "accepted" o "declined"

        if not all([quote_id, carrier_admin_id, rate, decision]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        if decision not in ["accepted", "declined"]:
            return jsonify({"status": "error", "message": "Invalid decision"}), 400
        
        quote = Quote.query.get(quote_id)
        carrier = Carrier.query.get(carrier_admin_id)

        
        if not quote or not carrier:
            return jsonify({"status": "error", "message": "Quote or Carrier not found"}), 404

        # Buscar el registro del rate
        quote_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote_id,
            carrier_id=carrier_admin_id,
            rate=rate
        ).first()

        if not quote_rate:
            return jsonify({"status": "error", "message": "Rate not found"}), 404

        # Actualizar el estado
        quote_rate.status = decision
        # quote_rate.decision_at = datetime.utcnow()

        db.session.commit()

        #

        #quote = Quote.query.get(quote_id)
        #carrier = Carrier.query.get(carrier_admin_id)

        if decision == "accepted":
            try:
                # Get shipper information
                shipper = Shipper.query.get(quote.shipper_id)
                shipper_name = f"{shipper.user.first_name} {shipper.user.last_name}" if shipper and shipper.user else "Unknown Shipper"
                
                # Render the award email HTML
                html_content = render_template(
                    "email/quote_awarded.html",
                    companyName=carrier.carrier_name,
                    shipperName=shipper_name,
                    quoteID=quote_id,
                    scac=carrier.scac,
                    rate=f"${float(rate):,.2f}",
                    mode=quote.mode,
                    equipmentType=quote.equipment_type,
                    temp=quote.temp_controlled,
                    origin=quote.origin,
                    destination=quote.destination,
                    commodity=quote.commodity,
                    weight=f"{float(quote.weight):,.0f} lbs" if quote.weight else "N/A",
                    declaredValue=f"${float(quote.declared_value):,.2f}" if quote.declared_value else "N/A",
                    comments=quote.comments or "None"
                )

                # Send email to carrier
                send_email(
                    recipient=carrier.user.email,
                    subject=f"Quote Awarded - {quote_id}",
                    body_text=f"Your quote for {quote_id} has been awarded.",
                    body_html=html_content
                )

            except Exception as e:
                print(f"Error sending award email: {str(e)}")
                # Don't fail the whole request if email fails
                pass
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("[ERROR] quote_decision:", str(e))
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app_routes.route("/api/lanes", methods=["GET"])
def get_lanes():
    """Get all frequent lanes for the current shipper"""
    try:
        # Get shipper ID from session
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
            
        shipper = Shipper.query.filter_by(user_id=user_id).first()
        if not shipper:
            return jsonify({"error": "Shipper not found"}), 404

        # Get lanes for this shipper only
        lanes = Lane.query.filter_by(shipper_id=shipper.id).order_by(Lane.created_at.desc()).all()
        
        lanes_data = []
        for lane in lanes:
            # Count carriers associated with this lane
            
            
            # Get last sent date (you might need to add this field to your model)
            #last_sent = lane.last_sent.strftime('%m/%d/%Y') if lane.last_sent else "Never"
            
            lanes_data.append({
                "id": lane.id,
                "nickname": lane.nickname,
                "origin": lane.origin,
                "destination": lane.destination,
                "equipment_type": lane.equipment_type,
                "carrier_count": 0,
                "last_sent": "",
                "created_at": lane.created_at.strftime('%m/%d/%Y') if lane.created_at else None
            })
            
        return jsonify({
            "status": "success", 
            "data": lanes_data,
            "total": len(lanes_data)
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/lanes/<int:lane_id>", methods=["GET"])
def get_lane(lane_id):
    """Get a specific frequent lane"""
    try:
        lane = Lane.query.get_or_404(lane_id)
        
        # Verify ownership (optional security check)
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        shipper = Shipper.query.filter_by(user_id=user_id).first()
        if lane.shipper_id != shipper.id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        lane_data = {
            "id": lane.id,
            "nickname": lane.nickname,
            "mode": lane.mode,
            "equipment_type": lane.equipment_type,
            "rate_type": lane.rate_type,
            "origin": lane.origin,
            "destination": lane.destination,
            "pickup_date": lane.pickup_date.isoformat() if lane.pickup_date else None,
            "delivery_date": lane.delivery_date.isoformat() if lane.delivery_date else None,
            "commodity": lane.commodity,
            "weight": float(lane.weight) if lane.weight else None,
            "declared_value": float(lane.declared_value) if lane.declared_value else None,
            "additional_stops": lane.additional_stops,
            "accessorials": [a.name for a in lane.accessorials],
            "comments": lane.comments,
            "created_at": lane.created_at.isoformat() if lane.created_at else None,
            "updated_at": lane.updated_at.isoformat() if lane.updated_at else None
        }
        
        return jsonify({"status": "success", "data": lane_data}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/lanes", methods=["POST"])
def create_lane():
    """Create a new frequent lane"""
    try:
        # Get form data from request
        data = request.form.to_dict()
        
        # Get user info from session
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        shipper = Shipper.query.filter_by(user_id=user_id).first()
        
        # Parse multi-select fields
        accessorials = request.form.getlist('accessorials[]')
        carrier_ids = request.form.getlist('carrier_ids[]')
        
        # Validate required fields
        required_fields = [
            'nickname', 'mode', 'equipment_type', 'rate_type',
            'origin', 'destination'
        ]
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
            
        # Convert dates
        pickup_date = None
        if data.get('pickup_date'):
            pickup_date = datetime.strptime(data['pickup_date'], '%Y-%m-%d').date()
            
        delivery_date = None
        if data.get('delivery_date'):
            delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
        
        # Create new lane
        new_lane = Lane(
            shipper_id=shipper.id,
            nickname=data['nickname'],
            mode=data['mode'],
            equipment_type=data['equipment_type'],
            rate_type=data['rate_type'],
            origin=data['origin'],
            destination=data['destination'],
            pickup_date=pickup_date,
            delivery_date=delivery_date,
            commodity=data.get('commodity', ''),
            weight=Decimal(str(data.get('weight', 0))),
            declared_value=Decimal(str(data.get('declared_value', 0))),
            comments=data.get('comments', ''),
            leave_open_for_option=data.get('leave_open_for_select', 'hours'),
            leave_open_for_number=int(data.get('number_leave_open_for', 24))
        )
        
        # Handle additional stops if provided
        if 'stops' in data:
            stops = []
            for stop_data in data['stops']:
                stops.append({
                    'location': stop_data['location'],
                    'type': stop_data['type']
                })
            new_lane.additional_stops = json.dumps(stops)
        
        # Handle accessorials if provided
        if accessorials:
            accessorial_objs = Accessorial.query.filter(
                Accessorial.name.in_(accessorials)
            ).all()
            new_lane.accessorials = accessorial_objs
            
        # Handle carriers if provided
        if carrier_ids and 'select_all' not in carrier_ids:
            carriers = Carrier.query.filter(
                Carrier.id.in_([int(id) for id in carrier_ids])
            ).all()
            new_lane.carriers = carriers
            
        db.session.add(new_lane)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Lane created successfully",
            "lane_id": new_lane.id
        }), 201
        
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Database integrity error"}), 400
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/lanes/<int:lane_id>", methods=["PUT", "POST"])
def update_lane(lane_id):
    """Update an existing frequent lane"""
    try:
        # Check if this is a PUT with form data (from our frontend)
        if request.method == "POST" and request.headers.get('X-HTTP-Method-Override') == 'PUT':
            data = request.form.to_dict()
            # Handle multi-value fields
            data['accessorials'] = request.form.getlist('accessorials[]')
            data['carrier_ids'] = request.form.getlist('carrier_ids[]')
        else:
            # Regular PUT with JSON
            data = request.get_json()

        lane = Lane.query.get_or_404(lane_id)
        
        # Verify ownership
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        shipper = Shipper.query.filter_by(user_id=user_id).first()

        if lane.shipper_id != shipper.id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        # Update basic fields
        update_fields = [
            'nickname', 'mode', 'equipment_type', 'rate_type',
            'origin', 'destination', 'commodity', 'comments'
        ]
        
        for field in update_fields:
            if field in data:
                setattr(lane, field, data[field])
                
        # Handle dates
        if 'pickup_date' in data and data['pickup_date']:
            lane.pickup_date = datetime.fromisoformat(data['pickup_date'])
        if 'delivery_date' in data and data['delivery_date']:
            lane.delivery_date = datetime.fromisoformat(data['delivery_date'])
            
        # Handle numeric fields
        if 'weight' in data:
            lane.weight = Decimal(str(data['weight'])) if data['weight'] else None
        if 'declared_value' in data:
            lane.declared_value = Decimal(str(data['declared_value'])) if data['declared_value'] else None
            
        # Handle additional stops
        if 'additional_stops' in data:
            if isinstance(data['additional_stops'], str):
                # If it's a string, parse it as JSON
                lane.additional_stops = json.loads(data['additional_stops'])
            else:
                lane.additional_stops = data['additional_stops']
            
        # Update accessorials
        if 'accessorials' in data:
            lane.accessorials = Accessorial.query.filter(
                Accessorial.name.in_(data['accessorials'])
            ).all()
            
        # Update carriers
        if 'carrier_ids' in data:
            # Remove existing carrier associations
            lane.carriers = []
            # Add new carriers
            carriers = Carrier.query.filter(Carrier.id.in_([int(id) for id in data['carrier_ids']])).all()
            lane.carriers.extend(carriers)
            
        lane.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Lane updated successfully",
            "data": {
                "id": lane.id,
                "nickname": lane.nickname,
                "origin": lane.origin,
                "destination": lane.destination,
                "equipment_type": lane.equipment_type,
                "carrier_count": len(lane.carriers),
            }
        }), 200
        
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Database integrity error"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/lanes/<int:lane_id>", methods=["DELETE"])
def delete_lane(lane_id):
    """Delete a frequent lane"""
    try:
        lane = Lane.query.get_or_404(lane_id)
        
        # Verify ownership
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        shipper = Shipper.query.filter_by(user_id=user_id).first()
        if lane.shipper_id != shipper.id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        db.session.delete(lane)
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Lane deleted successfully"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app_routes.route("/api/quote/decline_all", methods=["POST"])
def decline_all_quote_carriers():
    try:
        data = request.get_json()
        quote_id = data.get("quote_id")

        if not quote_id:
            return jsonify({"status": "error", "message": "Quote ID is required"}), 400

        # Get all quote carrier rates for this quote
        quote_rates = QuoteCarrierRate.query.filter_by(
            quote_id=quote_id
        ).all()

        if not quote_rates:
            return jsonify({"status": "error", "message": "No carriers found for this quote"}), 404

        # Update all rates to declined status
        for rate in quote_rates:
            rate.status = "declined"

        # Also update the quote status if you have one
        quote = Quote.query.get(quote_id)
        if quote:
            quote.status = "declined"  # Add this field to your Quote model if needed

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Declined all {len(quote_rates)} carriers for quote {quote_id}"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app_routes.route('/api/shipper/<int:id>/toggle_active', methods=['PUT'])
def toggle_shipper_active(id):
    shipper = Shipper.query.get_or_404(id)
    shipper.active = not shipper.active
    shipper.user.active = shipper.active
    db.session.commit()
    return jsonify({
        "status": "success",
        "active": shipper.active
    })

@app_routes.route("/api/quotes/nuke_all", methods=["DELETE"])
def nuke_all_quotes():
    try:
        # Eliminar registros relacionados primero para evitar errores de FK
        db.session.execute(quote_carrier.delete())  # Tabla de relación muchos-a-muchos
        
        # Eliminar rates asociados
        QuoteCarrierRate.query.delete()
        
        # Eliminar TODOS los quotes sin filtros
        num_deleted = Quote.query.delete()
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"🔥 Nuked {num_deleted} quotes and all related records",
            "warning": "This action is irreversible!"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Failed to nuke quotes: {str(e)}"
        }), 500
    
@app_routes.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Initialize stats with default values
        stats = {
            "pending_quotes": 0,
            "active_shippers": 0,
            "active_carriers": 0,
            "active_companies": 0,
            "spendMT": 0,  # Quotes assigned with values
            "completedQuotes": 0  # Quotes completed
        }

        # Subquery: quotes that have been accepted or declined
        excluded_quotes_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
            QuoteCarrierRate.status.in_(["accepted", "declined"])
        ).distinct().subquery()

        # Get counts based on user role
        if user.role == "Admin":
            stats.update({
                "pending_quotes": Quote.query.filter(
                    ~Quote.id.in_(excluded_quotes_subquery)
                ).count(),
                "active_shippers": Shipper.query.filter_by(
                    active=True, deleted=False
                ).count(),
                "active_carriers": Carrier.query.filter_by(active=True).count(),
                "active_companies": Company.query.filter_by(active=True).count(),
                "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate)).filter(
                    QuoteCarrierRate.status == "accepted"
                ).scalar() or 0,
                "completedQuotes": QuoteCarrierRate.query.filter(
                    QuoteCarrierRate.status == "accepted"
                ).count()
            })

        elif user.role == "Shipper":
            shipper = Shipper.query.filter_by(user_id=user_id).first()
            if shipper:
                stats.update({
                    "pending_quotes": Quote.query.filter(
                        Quote.shipper_id == shipper.id,
                        ~Quote.id.in_(excluded_quotes_subquery)
                    ).count(),
                    "active_shippers": 1,  # Themselves
                    "active_carriers": db.session.query(Carrier).join(
                        carrier_shipper
                    ).filter(
                        carrier_shipper.c.shipper_id == shipper.id,
                        Carrier.active == True
                    ).count(),
                    "active_companies": 1,  # Their company
                    "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate)).join(
                        Quote
                    ).filter(
                        Quote.shipper_id == shipper.id,
                        QuoteCarrierRate.status == "accepted"
                    ).scalar() or 0,
                    "completedQuotes": db.session.query(QuoteCarrierRate).join(
                        Quote
                    ).filter(
                        Quote.shipper_id == shipper.id,
                        QuoteCarrierRate.status == "accepted"
                    ).count()
                })

        elif user.role == "CompanyShipper":
            # First get the company associated with this CompanyShipper user
            company = Company.query.filter_by(user_id=user_id).first()
            if company:
                # Get all active shippers belonging to this company
                company_shippers = Shipper.query.filter_by(
                    company_id=company.id,
                    active=True,
                    deleted=False
                ).all()
                shipper_ids = [s.id for s in company_shippers]

                # Get carriers associated with this company through the association table
                # First ensure the association table is properly imported/defined
                
                
                stats.update({
                    "pending_quotes": Quote.query.filter(
                        Quote.shipper_id.in_(shipper_ids),
                        ~Quote.id.in_(excluded_quotes_subquery)
                    ).count(),
                    "active_shippers": len(shipper_ids),
                    "active_carriers": 0,
                    "active_companies": 1,  # Their own company
                    "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate))
                        .join(Quote)
                        .filter(
                            Quote.shipper_id.in_(shipper_ids),
                            QuoteCarrierRate.status == "accepted"
                        ).scalar() or 0,
                    "completedQuotes": db.session.query(QuoteCarrierRate)
                        .join(Quote)
                        .filter(
                            Quote.shipper_id.in_(shipper_ids),
                            QuoteCarrierRate.status == "accepted"
                        ).count(),
                    "completedToday": db.session.query(QuoteCarrierRate)
                        .join(Quote)
                        .filter(
                            Quote.shipper_id.in_(shipper_ids),
                            QuoteCarrierRate.status == "accepted"
                        ).count(),
                })

        elif user.role == "CarrierAdmin":
            carrier = Carrier.query.filter_by(user_id=user_id).first()
            if carrier:
                stats.update({
                    "pending_quotes": db.session.query(Quote).join(
                        quote_carrier
                    ).filter(
                        quote_carrier.c.carrier_id == carrier.id,
                        ~db.session.query(QuoteCarrierRate).filter(
                            QuoteCarrierRate.quote_id == Quote.id,
                            QuoteCarrierRate.carrier_admin_id == carrier.user_id,
                            QuoteCarrierRate.status.in_(["accepted", "declined"])
                        ).exists()
                    ).count(),
                    "active_shippers": db.session.query(Shipper).join(
                        carrier_shipper
                    ).filter(
                        carrier_shipper.c.carrier_id == carrier.id,
                        Shipper.active == True
                    ).count(),
                    "active_carriers": 1,  # Themselves
                    "active_companies": 1,  # Their company
                    "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate)).filter(
                        QuoteCarrierRate.carrier_admin_id == user_id,
                        QuoteCarrierRate.status == "accepted"
                    ).scalar() or 0,
                    "completedQuotes": QuoteCarrierRate.query.filter(
                        QuoteCarrierRate.carrier_admin_id == user_id,
                        QuoteCarrierRate.status == "accepted"
                    ).count()
                })

        return jsonify({
            "user_name": f"{user.first_name} {user.last_name}",
            "stats": stats
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get dashboard stats: {str(e)}"
        }), 500
    

@app_routes.route("/api/carrier/<int:carrier_id>/creator", methods=["GET"])
# @token_required  # Uncomment if you need authentication
def get_carrier_creator(carrier_id):
    carrier = Carrier.query.filter_by(user_id=carrier_id).first()
    
    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404
    
    if not carrier.created_by:
        return jsonify({"error": "Creator information not available"}), 404
    
    creator = User.query.get(carrier.created_by)
    
    if not creator:
        return jsonify({"error": "Creator user not found"}), 404
    
    # Assuming you have a Shipper model related to User
    shipper = Shipper.query.filter_by(user_id=creator.id).first()
    
    response_data = {
        "creator_id": creator.id,
        "first_name": creator.first_name,
        "last_name": creator.last_name,
        "email": creator.email,
        "phone": creator.phone,
        "created_at": creator.created_at.isoformat() if creator.created_at else None,
        "shipper_info": {
            "shipper_id": shipper.id if shipper else None,
            "company_name": shipper.company.company_name if shipper and shipper.company else None,
            "duns_number": shipper.company.duns if shipper and shipper.company else None
        } if shipper else None
    }
    
    return jsonify(response_data)
