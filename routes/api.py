import boto3
from database import db
from flask import jsonify, request, session, render_template
from routes import app_routes
from config import Config
from models import User, Company, Shipper, Carrier, Mode, EquipmentType, RateType, Accessorial
from models.association import carrier_shipper
from sqlalchemy.exc import IntegrityError
#from utils.token_required import token_required
from utils.send_email import send_email
from cryptography.fernet import Fernet
from config import Config
from datetime import datetime


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
            shippers = Shipper.query.filter_by(active=True).all()
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
        
        shippers = Shipper.query.filter_by(company_id=company.id, active=True).all()

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

    if request.method == "POST":
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
    if request.method == "GET":
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401
        carriers = Carrier.query.filter_by(active=True, created_by=user_id).all()
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
        user_id = session.get("user_id")
        data = request.form

        if(data.get("simple_carrier") == "true"):
            try:

                carrier = Carrier.query.get(user_id)

                f = Fernet(Config.HASH_KEY)
                encrypted_email = f.encrypt(data.get("email").encode()).decode()

                # Send the hashed email via POST
                register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"

                new_user = User(
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    email=data.get("email"),
                    phone=data.get("phone"),
                    role="Carrier",
                    active=True
                )
                db.session.add(new_user)
                db.session.flush()

                new_carrier = Carrier(
                    carrier_name=data.get("first_name"),
                    active=data.get("active", True),
                    user_id=new_user.id,
                    created_by=user_id,
                )

                db.session.add(new_carrier)
                db.session.flush()

                db.session.commit()

                try:
                    html_content = render_template(
                        "email/carrier_welcome_email.html",
                        shipper_name=f"{carrier.user.first_name} {carrier.user.last_name}",
                        contact_name=data["carrier_name"],
                        invite_url=register_url,
                        current_year=datetime.utcnow().year
                    )

                    response = send_email(
                        recipient=data.get("contact_email"),
                        subject="You're invited to QuoteZen!",
                        body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                        body_html=html_content
                    )
                except Exception as e:
                    print(f"Email error: {str(e)}")

                return jsonify(
                    {
                        "status": "success", 
                        "message": "Shipper created", 
                        "complete_registration": register_url
                    }), 200
            
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    "status": "error", 
                    "message": str(e), 
                }), 400

        try:
            shipper = Shipper.query.filter_by(user_id=user_id).first()

            f = Fernet(Config.HASH_KEY)
            encrypted_email = f.encrypt(data["contact_email"].encode()).decode()

            # Send the hashed email via POST
            register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"

            if not shipper:
                return jsonify({"success": False, "message": "Shipper not found"}), 404
            
            new_user = User(
                first_name=data.get("contact_name"),
                last_name=data.get("contact_name"),
                email=data.get("contact_email"),
                phone=data.get("contact_phone"),
                role="CarrierAdmin",
                active=True
            )
            db.session.add(new_user)
            db.session.flush()

            new_carrier = Carrier(
                carrier_name=data.get("carrier_name"),
                authority=data.get("authority"),
                scac=data.get("scac"),
                mc_number=data.get("mc_number"),
                active=data.get("active", True),
                user_id=new_user.id,
                created_by=user_id,
            )

            db.session.add(new_carrier)
            db.session.flush()

            new_carrier.shippers.append(shipper)

            db.session.commit()

            try:
                html_content = render_template(
                    "email/carrier_welcome_email.html",
                    shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
                    contact_name=data["carrier_name"],
                    invite_url=register_url,
                    current_year=datetime.utcnow().year
                )

                response = send_email(
                    recipient=data["contact_email"],
                    subject="You're invited to QuoteZen!",
                    body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                    body_html=html_content
                )
            except Exception as e:
                print(f"Email error: {str(e)}")

            return jsonify(
                {
                    "status": "success", 
                    "message": "Shipper created", 
                    "complete_registration": register_url
                }), 200

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "status": "error", 
                "message": str(e), 
            }), 400
    
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
        carrier.active = False  # Set active flag to False instead of deleting
        db.session.commit()

        return jsonify({"status": "success", "message": "Carrier deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Deletion failed: {str(e)}"}), 500

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

    # Get all user_ids that belong to carriers created directly or indirectly by this user
    created_user_ids = get_all_created_user_ids(user_id)

    # Get all carriers where created_by is in that list
    carriers = Carrier.query.filter(
        Carrier.active == True,
        Carrier.created_by.in_(created_user_ids)
    ).all()

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
