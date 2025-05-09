from decimal import Decimal
import json
import re
import boto3
from psycopg2 import DataError
from sqlalchemy import and_, func, or_, text
from botocore.exceptions import ClientError
import secrets
from itsdangerous import URLSafeTimedSerializer

from app.controller import create_carrier_user, create_carrier_admin
from app.database import db
from flask import jsonify, request, session, render_template
from app.routes import app_routes
from app.config import Config
from app.models import (
    User,
    Company,
    Shipper,
    Carrier,
    Mode,
    EquipmentType,
    RateType,
    Accessorial,
    City,
    Quote,
    QuoteCarrierRate,
)


from app.models.association import (
    carrier_shipper,
    quote_carrier,
)  # si lo tienes separado
from sqlalchemy.exc import IntegrityError

# from utils.token_required import token_required
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


serializer = URLSafeTimedSerializer(Config.SECRET_KEY)


def generate_reset_token(email):
    """Generate a secure token for password reset"""
    return serializer.dumps(email, salt=Config.PASSWORD_RESET_SALT)

def verify_reset_token(token, expiration=Config.PASSWORD_RESET_EXPIRE_HOURS*3600):
    """Verify the reset token and return email if valid"""
    try:
        email = serializer.loads(
            token,
            salt=Config.PASSWORD_RESET_SALT,
            max_age=expiration
        )
        return email
    except Exception as e:
        print(f"Token verification failed: {str(e)}")
        return None


@app_routes.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({"status": "API is running!"})


@app_routes.route("/api/signin", methods=["POST"])
def api_sign_in():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return (
            jsonify({"status": "error", "message": "Missing username or password."}),
            400,
        )

    client = boto3.client("cognito-idp", region_name=Config.COGNITO_REGION)

    try:
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            },
            ClientId=Config.CLIENT_ID,
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

        return jsonify(
            {
                "status": "success",
                "message": "Login successful!",
                "redirect_url": redirect_url,
                "user": {"id": user.id, "email": user.email, "role": user.role},
            }
        )

    except client.exceptions.NotAuthorizedException as e:
        print(Config.CLIENT_ID)
        print(f"Login error: {str(e)}")
        return (
            jsonify({"status": "error", "message": "Invalid username or password."}),
            401,
        )
    except client.exceptions.UserNotFoundException:
        return jsonify({"status": "error", "message": "User not found."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500



@app_routes.route("/api/forgot_password", methods=["POST"])
def api_forgot_password():
    try:
        data = request.get_json()
        email = data.get("email")
        
        if not email:
            return jsonify({
                "status": "error",
                "message": "Email is required"
            }), 400
            
        # Enhanced email validation
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
            return jsonify({
                "status": "error",
                "message": "Please enter a valid email address"
            }), 400

        # Initialize Cognito client
        cognito = boto3.client("cognito-idp", region_name=Config.COGNITO_REGION)
        
        try:
            # Step 1: Initiate password reset with Cognito
            response = cognito.forgot_password(
                ClientId=Config.CLIENT_ID,
                Username=email
            )
            
            print("Cognito forgot_password response:", response)

            # Step 2: Generate reset token and link
            reset_token = generate_reset_token(email)
            reset_link = f"{Config.FRONTEND_URL}/reset-password?token={reset_token}"
            
            # Step 3: Send email via SES
            ses = boto3.client('ses', region_name=Config.AWS_REGION)
            
            try:
                # Verify SES identity first
                ses.get_identity_verification_attributes(
                    Identities=[Config.SES_SENDER_EMAIL]
                )
                
                # Send the email
                response = ses.send_email(
                    Source=Config.SES_SENDER_EMAIL,
                    Destination={'ToAddresses': [email]},
                    Message={
                        'Subject': {'Data': 'Password Reset Instructions'},
                        'Body': {
                            'Text': {
                                'Data': f'Click this link to reset your password: {reset_link}\n'
                                        'This link will expire in 24 hours.'
                            },
                            'Html': {
                                'Data': f'''
                                <html>
                                <body style="font-family: Arial, sans-serif;">
                                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                                        <h2 style="color: #4e73df;">Password Reset</h2>
                                        <p>We received a request to reset your password.</p>
                                        <p>Click the button below to reset your password:</p>
                                        <a href="{reset_link}" 
                                           style="background-color: #4e73df; color: white; 
                                                  padding: 12px 24px; text-decoration: none; 
                                                  border-radius: 4px; display: inline-block;">
                                            Reset Password
                                        </a>
                                        <p style="margin-top: 20px;">Or copy this link:<br>
                                        <code style="word-break: break-all;">{reset_link}</code></p>
                                        <p style="font-size: 12px; color: #666;">
                                            This link expires in 24 hours.<br>
                                            If you didn't request this, please ignore this email.
                                        </p>
                                    </div>
                                </body>
                                </html>
                                '''
                            }
                        }
                    }
                )
                print("SES email sent successfully:", response)
                
                return jsonify({
                    "status": "success",
                    "message": "Password reset email sent. Please check your inbox."
                }), 200
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_msg = e.response['Error']['Message']
                print(f"SES Error ({error_code}): {error_msg}")
                
                if error_code == 'MessageRejected':
                    return jsonify({
                        "status": "error",
                        "message": "Email sending failed. Please contact support."
                    }), 500
                else:
                    return jsonify({
                        "status": "error",
                        "message": "Failed to send password reset email",
                        "error": error_msg
                    }), 500
                    
        except cognito.exceptions.UserNotFoundException:
            # Return generic success message for security
            return jsonify({
                "status": "success",
                "message": "If this email is registered, you'll receive a reset link"
            }), 200
            
        except cognito.exceptions.LimitExceededException:
            return jsonify({
                "status": "error",
                "message": "Too many attempts. Please try again later."
            }), 429
            
        except Exception as e:
            print(f"Cognito error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Failed to initiate password reset"
            }), 500

    except Exception as e:
        print(f"System error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500


def handle_password_reset_fallback(email):
    """Fallback method when Cognito email fails"""
    try:
        # Generate a custom reset code
        reset_code = generate_reset_code()
        
        # Store the code in your database (pseudo-code)
        # store_reset_code(email, reset_code)
        
        # Send via SES
        ses = boto3.client('ses', region_name=Config.AWS_REGION)
        reset_link = f"{Config.FRONTEND_URL}/reset-password?code={reset_code}&email={email}"
        
        response = ses.send_email(
            Source=Config.SES_SENDER_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': 'Password Reset Instructions'},
                'Body': {
                    'Text': {
                        'Data': f'Use this link to reset your password: {reset_link}'
                    },
                    'Html': {
                        'Data': f'''
                        <html>
                        <body>
                            <h2>Password Reset</h2>
                            <p>Click <a href="{reset_link}">here</a> to reset your password.</p>
                            <p>Or copy this link: {reset_link}</p>
                        </body>
                        </html>
                        '''
                    }
                }
            }
        )
        
        return jsonify({
            "status": "success",
            "message": "Password reset email sent (fallback method)"
        }), 200
        
    except Exception as e:
        print("Fallback password reset failed:", str(e))
        return jsonify({
            "status": "error",
            "message": "Failed to send password reset email"
        }), 500


def generate_reset_code():
    """Generate a secure reset code"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


@app_routes.route("/api/company", methods=["GET", "POST"])
# @token_required
def api_company():
    if request.method == "GET":
        creator_id = session.get("user_id")
        companies = Company.query.filter_by(active=True, created_by=creator_id)
        return jsonify(
            [
                {
                    "id": company.id,
                    "company_name": company.company_name,
                    "duns": company.duns,
                    "active": company.active,
                    "user": (
                        {
                            "first_name": company.user.first_name,
                            "phone": company.user.phone,
                            "address": company.user.address,
                            "email": company.user.email,
                            "active": company.user.active,
                        }
                        if company.user
                        else None
                    ),
                }
                for company in companies
            ]
        )
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
            if not all([
                company_name,
                duns,
                contact_name,
                contact_phone,
                address,
                contact_email,
            ]):
                return (
                    jsonify({"status": "error", "message": "All fields are required"}),
                    400,
                )

            # Check if email already exists
            existing_user = User.query.filter_by(email=contact_email).first()
            if existing_user:
                return (
                    jsonify({"status": "error", "message": "A user with this email already exists"}),
                    400,
                )

            # Check if DUNS already exists
            existing_company = Company.query.filter_by(duns=duns).first()
            if existing_company:
                return (
                    jsonify({"status": "error", "message": "A company with this DUNS number already exists"}),
                    400,
                )

            f = Fernet(Config.HASH_KEY)
            encrypted_email = f.encrypt(contact_email.encode()).decode()

            # Rest of your code remains the same...
            register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"
            creator_id = session.get("user_id")
            
            company_user = User(
                first_name=contact_name,
                last_name="",
                email=contact_email,
                phone=contact_phone,
                address=address,
                role="CompanyShipper",
            )
            
            db.session.add(company_user)
            db.session.commit()
            
            new_company = Company(
                company_name=company_name,
                duns=duns,
                user_id=company_user.id,
                created_by=creator_id,
            )
            
            db.session.add(new_company)
            db.session.commit()
            
            try:
                html_content = render_template(
                    "email/company_welcome_email.html", register_url=register_url
                )
                print(html_content)

                response = send_email(
                    recipient=contact_email,
                    subject="Welcome to QuoteZen!",
                    body_text="Welcome to QuoteZen! Please complete your registration.",
                    body_html=html_content,
                )
            except Exception as e:
                print(f"Email error: {str(e)}")

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Company created",
                        "complete_registration": register_url,
                    }
                ),
                200,
            )

        except Exception as e:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "An unexpected error occurred. Please try again later.",
                    }
                ),
                500,
            )


@app_routes.route("/api/company/<int:company_id>", methods=["GET"])
# @token_required
def get_company_by_id(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"status": "error", "message": "Company not found"}), 404

    return jsonify(
        {
            "id": company.id,
            "company_name": company.company_name,
            "duns": company.duns,
            "user": (
                {
                    "first_name": company.user.first_name,
                    "phone": company.user.phone,
                    "address": company.user.address,
                    "email": company.user.email,
                }
                if company.user
                else None
            ),
        }
    )


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
        return jsonify(
            {"status": "success", "message": "Company updated successfully!"}
        )
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify({"status": "error", "message": "DUNS number must be unique"}),
            400,
        )
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
# @token_required
def api_shipper():
    if request.method == "GET":
        role_user = session.get("user_role")
        if role_user == "Admin":
            shippers = Shipper.query.filter_by(deleted=False).all()
            return jsonify(
                [
                    {
                        "id": shipper.id,
                        "company_id": shipper.company_id,
                        "active": shipper.active,
                        "user": (
                            {
                                "first_name": shipper.user.first_name,
                                "last_name": shipper.user.last_name,
                                "phone": shipper.user.phone,
                                "email": shipper.user.email,
                                "active": shipper.user.active,
                            }
                            if shipper.user
                            else None
                        ),
                    }
                    for shipper in shippers
                ]
            )

        user_id = session.get("user_id")
        company = Company.query.filter_by(user_id=user_id).first()
        if not company:
            return jsonify([])

        shippers = Shipper.query.filter_by(company_id=company.id).all()

        return jsonify(
            [
                {
                    "id": shipper.id,
                    "company_id": shipper.company_id,
                    "active": shipper.active,
                    "deleted": shipper.deleted,
                    "user": (
                        {
                            "first_name": shipper.user.first_name,
                            "last_name": shipper.user.last_name,
                            "phone": shipper.user.phone,
                            "email": shipper.user.email,
                            "active": shipper.user.active,
                        }
                        if shipper.user
                        else None
                    ),
                }
                for shipper in shippers
            ]
        )

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
            register_url = (
                f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"
            )

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
                active=True,
            )
            db.session.add(new_user)
            db.session.flush()

            # Create shipper
            new_shipper = Shipper(
                user_id=new_user.id,
                company_id=company.id,
                created_by=user_id,
                active=True,
            )
            db.session.add(new_shipper)
            db.session.commit()

            try:
                html_content = render_template(
                    "email/shipper_welcome_email.html",
                    name=f"{first_name} {last_name}",
                    userAdminName=company.company_name,
                    link_to_create_password=register_url,
                )

                print(html_content)

                response = send_email(
                    recipient=email,
                    subject="You're invited to QuoteZen!",
                    body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                    body_html=html_content,
                )
            except Exception as e:
                print(f"Email error: {str(e)}")

            # Return new table row for HTMX
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Shipper created",
                        "complete_registration": register_url,
                    }
                ),
                200,
            )

        except Exception as e:
            db.session.rollback()
            # Handle specific SQLAlchemy errors
            if "UniqueViolation" in str(e) and "uq_user_email" in str(e):
                return jsonify({
                    "success": False, 
                    "message": "This email address is already registered. Please use a different email."
                }), 400
            else:
                return jsonify({
                    "success": False, 
                    "message": "An unexpected error occurred. Please try again later."
                }), 500


@app_routes.route("/api/shipper/<int:shipper_id>", methods=["GET"])
# @token_required
def get_shipper_by_id(shipper_id):
    shipper = Shipper.query.get(shipper_id)
    if not shipper:
        return jsonify({"status": "error", "message": "Shipper not found"}), 404

    return jsonify(
        {
            "id": shipper.id,
            "company_id": shipper.company_id,
            "active": shipper.active,
            "user": (
                {
                    "first_name": shipper.user.first_name,
                    "last_name": shipper.user.last_name,
                    "phone": shipper.user.phone,
                    "email": shipper.user.email,
                    "active": shipper.user.active,
                }
                if shipper.user
                else None
            ),
        }
    )


@app_routes.route("/api/shipper/<int:shipper_id>", methods=["PUT"])
# @token_required
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
        return (
            jsonify({"status": "error", "message": "DUNS number must be unique"}),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {"status": "error", "message": f"Failed to update shipper: {str(e)}"}
            ),
            500,
        )


@app_routes.route("/api/shipper/<int:shipper_id>", methods=["DELETE"])
# @token_required
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
        return (
            jsonify({"status": "success", "message": "Shipper deleted successfully"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app_routes.route("/api/carrier/", methods=["GET", "POST"])
# @token_required
def api_carrier():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    if request.method == "GET":
        user = User.query.get(user_id)
        
        if user.role == 'CarrierAdmin':
            carriers = Carrier.query.filter_by(created_by=user_id).all()
            carrier_list = [
                {
                    "id": carrier.id,
                    "carrier_name": carrier.carrier_name,
                    "authority": carrier.authority,
                    "scac": carrier.scac,
                    "mc_number": carrier.mc_number,
                    "active": carrier.active,
                    "created_at": carrier.created_at.isoformat() if carrier.created_at else None,
                    "updated_at": carrier.updated_at.isoformat() if carrier.updated_at else None,
                    "user": {
                        "id": carrier.primary_user.id,
                        "first_name": carrier.primary_user.first_name,
                        "last_name": carrier.primary_user.last_name,
                        "email": carrier.primary_user.email,
                        "phone": carrier.primary_user.phone
                    } if carrier.primary_user else None
                }
                for carrier in carriers
            ]
            return jsonify(carrier_list), 200
        else:
            shipper = Shipper.query.filter_by(user_id=user_id).first()
            if not shipper:
                return jsonify({"error": "Shipper not found"}), 404

            # Get all shippers from the same company
            company_shippers = Shipper.query.filter_by(company_id=shipper.company_id).all()

            # Get all carriers associated with these shippers
            carriers = Carrier.query.filter(
                Carrier.shippers.any(Shipper.id.in_([s.id for s in company_shippers]))
            ).distinct()

            def get_carrier_full_data(carrier, current_shipper_id):
                """Get complete carrier data including primary user and ownership info"""
                carrier_data = {
                    "id": carrier.id,
                    "carrier_name": carrier.carrier_name,
                    "authority": carrier.authority,
                    "scac": carrier.scac,
                    "mc_number": carrier.mc_number,
                    "active": carrier.active,
                    "created_at": carrier.created_at.isoformat(),
                    "updated_at": carrier.updated_at.isoformat(),
                    "belongs_to_current_shipper": any(
                        s.id == current_shipper_id for s in carrier.shippers
                    ),
                    "user": None,
                    "created_by": None
                }
                
                # Get primary user data (from primary_user relationship)
                if carrier.primary_user:
                    carrier_data["user"] = {
                        "id": carrier.primary_user.id,
                        "first_name": carrier.primary_user.first_name,
                        "last_name": carrier.primary_user.last_name,
                        "email": carrier.primary_user.email,
                        "phone": carrier.primary_user.phone,
                        "active": carrier.primary_user.active,
                        "role": getattr(carrier.primary_user, 'role', None)
                    }
                
                # Get creator info (from created_by_user relationship)
                if carrier.created_by_user:
                    carrier_data["created_by"] = {
                        "user_id": carrier.created_by_user.id,
                        "name": f"{carrier.created_by_user.first_name} {carrier.created_by_user.last_name}",
                        "email": carrier.created_by_user.email
                    }
                
                return carrier_data

            # Build complete carrier list
            carrier_list = [get_carrier_full_data(carrier, shipper.id) for carrier in carriers]

            # Optional: Sort with current shipper's carriers first
            carrier_list.sort(key=lambda x: not x["belongs_to_current_shipper"])

            return jsonify(carrier_list), 200

    if request.method == "POST":
        data = request.form
        if data.get("simple_carrier") == "true":
            return create_carrier_user(data=data, user_id=user_id, db=db)
        else:
            return create_carrier_admin(data=data, user_id=user_id, db=db)
        

def get_user_data_shipper(carrier, target_shipper_id):
    """
    Obtiene los datos del usuario asociado a un shipper específico desde un carrier
    """
    if not target_shipper_id:
        return None
    
    # Encontrar la relación entre este carrier y el shipper objetivo
    for shipper_rel in carrier.shippers:
        if shipper_rel.id == target_shipper_id:
            # Obtener el usuario asociado a este shipper
            user = shipper_rel.user
            return {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "email": user.email,
                "active": user.active,
                "role": getattr(user, 'role', None)
            }
    return None

@app_routes.route("/api/carrier/<string:mc_number>", methods=["GET"])
# @token_required
def get_carrier_by_mc(mc_number):

    carrier = Carrier.query.filter_by(
        mc_number=mc_number,
        active=True,
    ).first()

    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404

    return jsonify(
        {
            "id": carrier.id,
            "carrier_name": carrier.carrier_name,
            "authority": carrier.authority,
            "scac": carrier.scac,
            "mc_number": carrier.mc_number,
            "active": carrier.active,
            "created_at": carrier.created_at.isoformat(),
            "updated_at": carrier.updated_at.isoformat(),
            "user": (
                {
                    "first_name": carrier.user.first_name,
                    "last_name": carrier.user.last_name,
                    "phone": carrier.user.phone,
                    "email": carrier.user.email,
                    "active": carrier.user.active,
                }
                if carrier.user
                else None
            ),
        }
    )


@app_routes.route("/api/carrier/<int:carrier_id>", methods=["GET"])
# @token_required
def get_carrier_by_id(carrier_id):
    user_id = session.get("user_id")
    shipper = Shipper.query.filter_by(user_id=user_id).first()
    carrier = Carrier.query.get(carrier_id)

    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404

    return jsonify(
        {
            "id": carrier.id,
            "carrier_name": carrier.carrier_name,
            "authority": carrier.authority,
            "scac": carrier.scac,
            "mc_number": carrier.mc_number,
            "active": carrier.active,
            "created_at": carrier.created_at.isoformat(),
            "updated_at": carrier.updated_at.isoformat(),
            "user": get_user_data_for_shipper(carrier.users, shipper.id),
        }
    )


@app_routes.route("/api/carrier/<int:carrier_id>", methods=["PUT"])
# @token_required
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

            '''
            user = carrier.user
            user.first_name = data.get("contact_name")
            user.last_name = data.get("contact_name")
            user.phone = data.get("contact_phone")
            user.email = data.get("contact_email")
            '''

        db.session.commit()

        return (
            jsonify({"status": "success", "message": "Carrier updated successfully"}),
            200,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Update failed: {str(e)}"}), 500


@app_routes.route("/api/carrier/<int:carrier_id>", methods=["DELETE"])
# @token_required
def delete_carrier(carrier_id):
    try:
        carrier = Carrier.query.get_or_404(carrier_id)
        carrier.deleted = True  # Set active flag to False instead of deleting
        db.session.commit()

        return jsonify({"status": "success", "message": "Carrier deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"status": "error", "message": f"Deletion failed: {str(e)}"}),
            500,
        )


@app_routes.route("/api/carrier/<int:carrier_id>/toggle-active", methods=["PUT"])
# @token_required
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
        return (
            jsonify({"status": "success", "message": f"Carrier {status} successfully"}),
            200,
        )

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
        carriers_created = Carrier.query.filter_by(
            created_by=current_user_id, active=True
        ).all()

        for carrier in carriers_created:
            if carrier.user_id:  # If carrier has a user
                queue.append(carrier.user_id)

    return visited


@app_routes.route("/api/carrier_quotes/", methods=["GET"])
def carrier_quotes():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    shipper = Shipper.query.filter_by(user_id=user_id).first()
    
    carriers = (
        Carrier.query.filter(
            Carrier.users.any(shipper_id=shipper.id),
            Carrier.active == True,
            Carrier.deleted == False,
        )
        .order_by(Carrier.carrier_name)
        .all()
    )

    print("Carriers:", carriers)

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
            "user": get_user_data_for_shipper(carrier.users, shipper.id),
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
                "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}",
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
                "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}",
            }
            for city in results_full
        ]
        return jsonify(response)

    # Si no hay resultados con el término completo, procedemos con el split
    search_terms = [t.strip() for t in term.replace(",", " ").split() if t.strip()]

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
                City.postal_code.ilike(f"%{single_term}%"),
            )
        )

    results = query.limit(10).all()

    response = [
        {
            "label": f"{city.city_name}, {city.province_abbr} {city.postal_code} ({city.country_name})",
            "value": f"{city.city_name}, {city.province_abbr} {city.postal_code}",
        }
        for city in results
    ]

    return jsonify(response)


def send_emails_to_carrier_company_and_users(shipper_id, selected_carriers, quote_id, shipper_name):
    """
    Sending email for carrier companies
    """
    try:
        f = Fernet(Config.HASH_KEY)
        encrypted_id = f.encrypt(str(quote_id).encode()).decode()
        # Send the hashed email via POST
        quote_url = f"{Config.DOMAIN_URL}/carrier_pending_quotes/{encrypted_id}"
        for carrier in selected_carriers:
            user = next((user for user in carrier.users if user.shipper_id == shipper_id), None)
            if user.email:
                html_content = render_template(
                    "email/quote.html",
                    quote_url=quote_url,
                    current_year=datetime.now().year,
                    carrier_name=carrier.carrier_name,
                    shipper_name=shipper_name,
                )

                response = send_email(
                    recipient=user.email,
                    subject="New Quote Available - Urgent",
                    body_text="You have a new quote available in QuoteZen.",
                    body_html=html_content,
                )
                print(f"Email sent to {user.email}: {response}")

            creator_carriers = Carrier.query.filter_by(created_by=user.id).all()
            for creator_carrier in creator_carriers:
                html_content = render_template(
                    "email/quote.html",
                    quote_url=quote_url,
                    current_year=datetime.now().year,
                    carrier_name=creator_carrier.carrier_name,
                    shipper_name=shipper_name,
                )

                for user in creator_carrier.users:
                    if user.shipper_id == shipper_id:
                        html_content = render_template(
                            "email/quote.html",
                            quote_url=quote_url,
                            current_year=datetime.now().year,
                            carrier_name=creator_carrier.carrier_name,
                            shipper_name=shipper_name,
                        )

                        response = send_email(
                            recipient=user.email,
                            subject="New Quote Available - Urgent",
                            body_text="You have a new quote available in QuoteZen.",
                            body_html=html_content,
                        )
                    print(
                        f"Email sent to creator's other carrier {user.email}: {response}"
                    )
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
                return (
                    jsonify({"status": "error", "message": "User is not a shipper"}),
                    403,
                )
            
            required_fields = [
                'mode', 'equipment_type', 'origin', 'destination', 'leave_open_value'
            ]
            
            missing_fields = [field for field in required_fields if not form.get(field)]
        
            if missing_fields:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required fields: {', '.join(missing_fields)}"
                }), 400

            carrier_ids = form.getlist("carrier_ids[]")

            if not carrier_ids:
                return (
                    jsonify({"status": "error", "message": "No carriers selected"}),
                    400,
                )

            stops_json = form.get("stops", "[]")  # Obtiene el string JSON
            additional_stops = json.loads(stops_json)  # Convierte a lista/dict
            print("Parsed stops:", additional_stops)

            # Query selected company carriers
            selected_carriers = Carrier.query.filter(Carrier.id.in_(carrier_ids)).all()
            carriers_of_company_carrier = Carrier.query.filter(
                Carrier.created_by.in_(carrier_ids)
            ).all()

            quote = Quote(
                mode=form.get("mode"),
                equipment_type=form.get("equipment_type"),
                rate_type=form.get("rate_type"),
                temp_controlled=False,
                origin=form.get("origin"),
                destination=form.get("destination"),
                pickup_date=(
                    datetime.strptime(form.get("pickup_date"), "%Y-%m-%d")
                    if form.get("pickup_date")
                    else None
                ),
                delivery_date=(
                    datetime.strptime(form.get("delivery_date"), "%Y-%m-%d")
                    if form.get("delivery_date")
                    else None
                ),
                commodity=form.get("commodity"),
                weight=float(form.get("weight") or 0),
                declared_value=float(form.get("declared_value") or 0),
                accessorials=",".join(form.getlist("accessorials[]")),
                comments=form.get("comments"),
                additional_stops=additional_stops,
                carriers=selected_carriers,
                open_unit=form.get("leave_open_unit"),
                open_value=form.get("leave_open_value"),
                shipper_id=shipper.id,
                temp=form.get('temp')
            )

            db.session.add(quote)
            db.session.commit()

            send_emails_to_carrier_company_and_users(
                shipper_id=shipper.id,
                selected_carriers=selected_carriers + carriers_of_company_carrier,
                quote_id=quote.id,
                shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
            )

            return jsonify({"status": "success", "quote_id": quote.id})

        except Exception as e:
            db.session.rollback()
            
            # Handle specific database errors
            if isinstance(e, (IntegrityError, DataError)):
                error_info = str(e.orig)
                
                if "null value in column" in error_info:
                    column = error_info.split('"')[1]
                    return jsonify({
                        "status": "error",
                        "message": f"Missing required field: {column.replace('_', ' ').title()}"
                    }), 400
                elif "violates foreign key constraint" in error_info:
                    return jsonify({
                        "status": "error",
                        "message": "Invalid reference data provided"
                    }), 400
                else:
                    return jsonify({
                        "status": "error",
                        "message": "Database error occurred. Please check your data."
                    }), 400
                    
            # Generic error handler
            return jsonify({
                "status": "error",
                "message": "An unexpected error occurred. Please try again later."
            }), 500


@app_routes.route("/api/quote/<int:quote_id>", methods=["GET"])
def get_quote_by_id(quote_id):
    quote = Quote.query.options(
        db.joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier),
        db.joinedload(Quote.carriers),
        db.joinedload(Quote.shipper).joinedload(Shipper.user)
    ).get(quote_id)
    
    if not quote:
        return jsonify({"status": "error", "message": "Quote not found"}), 404

    # Convert the additional_stops JSON string to a Python object
    try:
        additional_stops = json.loads(quote.additional_stops) if quote.additional_stops else []
    except json.JSONDecodeError:
        additional_stops = []

    # Prepare rates data
    rates_data = []
    for rate in quote.quote_rates:
        carrier = rate.carrier
        user = User.query.get(rate.user_id) if rate.user_id else None
        
        rates_data.append({
            "id": rate.id,
            "carrier_id": carrier.id if carrier else None,
            "carrier_name": carrier.carrier_name if carrier else "Unknown Carrier",
            "scac": carrier.scac if carrier else None,
            "mc_number": carrier.mc_number if carrier else None,
            "rate": float(rate.rate) if rate.rate else None,
            "comment": rate.comment,
            "status": rate.status,
            "submitted_at": rate.created_at.isoformat() if rate.created_at else None,
            "submitted_by": f"{user.first_name} {user.last_name}" if user else "System",
            "user_role": user.role if user else None
        })

    # Calculate rates summary
    valid_rates = [r for r in rates_data if r['rate'] is not None]
    rates_summary = {
        "count": len(valid_rates),
        "accepted": len([r for r in rates_data if r['status'] == 'accepted']),
        "pending": len([r for r in rates_data if r['status'] not in ['accepted', 'declined']]),
        "lowest": min([r['rate'] for r in valid_rates], default=None),
        "highest": max([r['rate'] for r in valid_rates], default=None),
        "average": sum([r['rate'] for r in valid_rates])/len(valid_rates) if valid_rates else None
    }

    shipper_info = None
    if quote.shipper and quote.shipper.user:
        shipper_info = {
            "id": quote.shipper.id,
            "name": f"{quote.shipper.user.first_name} {quote.shipper.user.last_name}",
            "email": quote.shipper.user.email,
            "company_id": quote.shipper.company_id
        }

    return jsonify({
        "status": "success",
        "quote": {
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
            "additional_stops": additional_stops,
            "open_unit": quote.open_unit,
            "open_value": quote.open_value,
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
            "status": "open",  # Puedes añadir lógica para determinar el estado
            "shipper": shipper_info
        },
        "rates": {
            "data": rates_data,
            "summary": rates_summary
        },
        "carriers": [{
            "id": c.id,
            "name": c.carrier_name,
            "scac": c.scac,
            "mc_number": c.mc_number
        } for c in quote.carriers]
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
        #user_carrier = Carrier.users.any(shipper_id=shipper.id)

        # Guardar historial en QuoteCarrierRate (auditoría)
        quote_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote_id, carrier_id=carrier_id
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
                carrier_admin_id=user_id,
                rate=rate,
                comment=comment,
                created_at=datetime.utcnow(),
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
            return (
                jsonify({"status": "error", "message": "Missing required fields"}),
                400,
            )

        if decision not in ["accepted", "declined"]:
            return jsonify({"status": "error", "message": "Invalid decision"}), 400

        quote = Quote.query.get(quote_id)
        carrier = Carrier.query.get(carrier_admin_id)

        if not quote or not carrier:
            return (
                jsonify({"status": "error", "message": "Quote or Carrier not found"}),
                404,
            )

        # Buscar el registro del rate
        quote_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote_id, carrier_id=carrier_admin_id, rate=rate
        ).first()

        if not quote_rate:
            return jsonify({"status": "error", "message": "Rate not found"}), 404

        # Actualizar el estado
        quote_rate.status = decision
        # quote_rate.decision_at = datetime.utcnow()

        db.session.commit()

        #

        # quote = Quote.query.get(quote_id)
        # carrier = Carrier.query.get(carrier_admin_id)

        if decision == "accepted":
            try:
                # Get shipper information
                shipper = Shipper.query.get(quote.shipper_id)
                shipper_name = (
                    f"{shipper.user.first_name} {shipper.user.last_name}"
                    if shipper and shipper.user
                    else "Unknown Shipper"
                )

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
                    declaredValue=(
                        f"${float(quote.declared_value):,.2f}"
                        if quote.declared_value
                        else "N/A"
                    ),
                    comments=quote.comments or "None",
                )

                # Send email to carrier
                send_email(
                    recipient=carrier.user.email,
                    subject=f"Quote Awarded - {quote_id}",
                    body_text=f"Your quote for {quote_id} has been awarded.",
                    body_html=html_content,
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
        lanes = (
            Lane.query.filter_by(shipper_id=shipper.id)
            .order_by(Lane.created_at.desc())
            .all()
        )

        lanes_data = []
        for lane in lanes:
            # Count carriers associated with this lane

            # Get last sent date (you might need to add this field to your model)
            # last_sent = lane.last_sent.strftime('%m/%d/%Y') if lane.last_sent else "Never"

            lanes_data.append(
                {
                    "id": lane.id,
                    "nickname": lane.nickname,
                    "origin": lane.origin,
                    "destination": lane.destination,
                    "equipment_type": lane.equipment_type,
                    "carrier_count": 0,
                    "last_sent": "",
                    "created_at": (
                        lane.created_at.strftime("%m/%d/%Y")
                        if lane.created_at
                        else None
                    ),
                }
            )

        return (
            jsonify(
                {"status": "success", "data": lanes_data, "total": len(lanes_data)}
            ),
            200,
        )

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
            "delivery_date": (
                lane.delivery_date.isoformat() if lane.delivery_date else None
            ),
            "commodity": lane.commodity,
            "weight": float(lane.weight) if lane.weight else None,
            "declared_value": (
                float(lane.declared_value) if lane.declared_value else None
            ),
            "additional_stops": lane.additional_stops,
            "accessorials": [a.name for a in lane.accessorials],
            "comments": lane.comments,
            "created_at": lane.created_at.isoformat() if lane.created_at else None,
            "updated_at": lane.updated_at.isoformat() if lane.updated_at else None,
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
        accessorials = request.form.getlist("accessorials[]")
        carrier_ids = request.form.getlist("carrier_ids[]")

        # Validate required fields
        required_fields = [
            "nickname",
            "mode",
            "equipment_type",
            "rate_type",
            "origin",
            "destination",
        ]

        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Missing required fields: {', '.join(missing_fields)}",
                    }
                ),
                400,
            )

        # Convert dates
        pickup_date = None
        if data.get("pickup_date"):
            pickup_date = datetime.strptime(data["pickup_date"], "%Y-%m-%d").date()

        delivery_date = None
        if data.get("delivery_date"):
            delivery_date = datetime.strptime(data["delivery_date"], "%Y-%m-%d").date()

        # Create new lane
        new_lane = Lane(
            shipper_id=shipper.id,
            nickname=data["nickname"],
            mode=data["mode"],
            equipment_type=data["equipment_type"],
            rate_type=data["rate_type"],
            origin=data["origin"],
            destination=data["destination"],
            pickup_date=pickup_date,
            delivery_date=delivery_date,
            commodity=data.get("commodity", ""),
            weight=Decimal(str(data.get("weight", 0))),
            declared_value=Decimal(str(data.get("declared_value", 0))),
            comments=data.get("comments", ""),
            leave_open_for_option=data.get("leave_open_for_select", "hours"),
            leave_open_for_number=int(data.get("number_leave_open_for", 24)),
        )

        # Handle additional stops if provided
        if "stops" in data:
            stops = []
            for stop_data in data["stops"]:
                stops.append(
                    {"location": stop_data["location"], "type": stop_data["type"]}
                )
            new_lane.additional_stops = json.dumps(stops)

        # Handle accessorials if provided
        if accessorials:
            accessorial_objs = Accessorial.query.filter(
                Accessorial.name.in_(accessorials)
            ).all()
            new_lane.accessorials = accessorial_objs

        # Handle carriers if provided
        if carrier_ids and "select_all" not in carrier_ids:
            carriers = Carrier.query.filter(
                Carrier.id.in_([int(id) for id in carrier_ids])
            ).all()
            new_lane.carriers = carriers

        db.session.add(new_lane)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Lane created successfully",
                    "lane_id": new_lane.id,
                }
            ),
            201,
        )

    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Database integrity error"}), 400
    except ValueError as e:
        db.session.rollback()
        return (
            jsonify({"status": "error", "message": f"Invalid data format: {str(e)}"}),
            400,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app_routes.route("/api/lanes/<int:lane_id>", methods=["PUT", "POST"])
def update_lane(lane_id):
    """Update an existing frequent lane"""
    try:
        # Check if this is a PUT with form data (from our frontend)
        if (
            request.method == "POST"
            and request.headers.get("X-HTTP-Method-Override") == "PUT"
        ):
            data = request.form.to_dict()
            # Handle multi-value fields
            data["accessorials"] = request.form.getlist("accessorials[]")
            data["carrier_ids"] = request.form.getlist("carrier_ids[]")
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
            "nickname",
            "mode",
            "equipment_type",
            "rate_type",
            "origin",
            "destination",
            "commodity",
            "comments",
        ]

        for field in update_fields:
            if field in data:
                setattr(lane, field, data[field])

        # Handle dates
        if "pickup_date" in data and data["pickup_date"]:
            lane.pickup_date = datetime.fromisoformat(data["pickup_date"])
        if "delivery_date" in data and data["delivery_date"]:
            lane.delivery_date = datetime.fromisoformat(data["delivery_date"])

        # Handle numeric fields
        if "weight" in data:
            lane.weight = Decimal(str(data["weight"])) if data["weight"] else None
        if "declared_value" in data:
            lane.declared_value = (
                Decimal(str(data["declared_value"])) if data["declared_value"] else None
            )

        # Handle additional stops
        if "additional_stops" in data:
            if isinstance(data["additional_stops"], str):
                # If it's a string, parse it as JSON
                lane.additional_stops = json.loads(data["additional_stops"])
            else:
                lane.additional_stops = data["additional_stops"]

        # Update accessorials
        if "accessorials" in data:
            lane.accessorials = Accessorial.query.filter(
                Accessorial.name.in_(data["accessorials"])
            ).all()

        # Update carriers
        if "carrier_ids" in data:
            # Remove existing carrier associations
            lane.carriers = []
            # Add new carriers
            carriers = Carrier.query.filter(
                Carrier.id.in_([int(id) for id in data["carrier_ids"]])
            ).all()
            lane.carriers.extend(carriers)

        lane.updated_at = datetime.utcnow()
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Lane updated successfully",
                    "data": {
                        "id": lane.id,
                        "nickname": lane.nickname,
                        "origin": lane.origin,
                        "destination": lane.destination,
                        "equipment_type": lane.equipment_type,
                        "carrier_count": len(lane.carriers),
                    },
                }
            ),
            200,
        )

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

        return (
            jsonify({"status": "success", "message": "Lane deleted successfully"}),
            200,
        )

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
        quote_rates = QuoteCarrierRate.query.filter_by(quote_id=quote_id).all()

        if not quote_rates:
            return (
                jsonify(
                    {"status": "error", "message": "No carriers found for this quote"}
                ),
                404,
            )

        # Update all rates to declined status
        for rate in quote_rates:
            rate.status = "declined"

        # Also update the quote status if you have one
        quote = Quote.query.get(quote_id)
        if quote:
            quote.status = "declined"  # Add this field to your Quote model if needed

        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Declined all {len(quote_rates)} carriers for quote {quote_id}",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app_routes.route("/api/shipper/<int:id>/toggle_active", methods=["PUT"])
def toggle_shipper_active(id):
    shipper = Shipper.query.get_or_404(id)
    shipper.active = not shipper.active
    shipper.user.active = shipper.active
    db.session.commit()
    return jsonify({"status": "success", "active": shipper.active})


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

        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"🔥 Nuked {num_deleted} quotes and all related records",
                    "warning": "This action is irreversible!",
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"status": "error", "message": f"Failed to nuke quotes: {str(e)}"}),
            500,
        )


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
            "spendMT": 0,
            "completedQuotes": 0,
        }

        now = datetime.utcnow()

        # Subquery: quotes that have been accepted or declined
        excluded_quotes_subquery = (
            db.session.query(QuoteCarrierRate.quote_id)
            .filter(QuoteCarrierRate.status.in_(["accepted", "declined"]))
            .distinct()
            .subquery()
        )

        # Condition to check for expired quotes
        expired_condition = or_(
            and_(
                Quote.open_unit == 'minutes',
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 minute'")) <= now
            ),
            and_(
                Quote.open_unit == 'hours',
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 hour'")) <= now
            ),
            and_(
                Quote.open_unit == 'days',
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 day'")) <= now
            )
        )

        # Get counts based on user role
        if user.role == "Admin":
            stats.update(
                {
                    "pending_quotes": Quote.query.filter(
                        ~Quote.id.in_(excluded_quotes_subquery),
                        ~expired_condition
                    ).count(),
                    "active_shippers": Shipper.query.filter_by(
                        active=True, deleted=False
                    ).count(),
                    "active_carriers": Carrier.query.filter_by(active=True).count(),
                    "active_companies": Company.query.filter_by(active=True).count(),
                    "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate))
                    .filter(QuoteCarrierRate.status == "accepted")
                    .scalar()
                    or 0,
                    "completedQuotes": QuoteCarrierRate.query.filter(
                        QuoteCarrierRate.status == "accepted"
                    ).count(),
                }
            )

        elif user.role == "Shipper":
            shipper = Shipper.query.filter_by(user_id=user_id).first()
            if shipper:
                # Get stats only for the logged-in shipper
                stats.update(
                    {
                        "pending_quotes": Quote.query.filter(
                            Quote.shipper_id == shipper.id,
                            ~Quote.id.in_(excluded_quotes_subquery),
                            ~expired_condition
                        ).count(),
                        "active_shippers": 1,  # Only counting the logged-in shipper
                        "active_carriers": db.session.query(Carrier)
                            .join(carrier_shipper)
                            .filter(
                                carrier_shipper.c.shipper_id == shipper.id,
                                Carrier.active == True
                            )
                            .distinct()
                            .count(),
                        "active_companies": 1 if shipper.company_id else 0,
                        "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate))
                            .join(Quote)
                            .filter(
                                Quote.shipper_id == shipper.id,
                                QuoteCarrierRate.status == "accepted",
                            )
                            .scalar()
                            or 0,
                        "completedQuotes": db.session.query(QuoteCarrierRate)
                            .join(Quote)
                            .filter(
                                Quote.shipper_id == shipper.id,
                                QuoteCarrierRate.status == "accepted",
                            )
                            .count(),
                    }
                )

        elif user.role == "CompanyShipper":
            company = Company.query.filter_by(user_id=user_id).first()
            if company:
                # Get all active shippers belonging to this company
                company_shippers = Shipper.query.filter_by(
                    company_id=company.id, active=True, deleted=False
                ).all()
                shipper_ids = [s.id for s in company_shippers]

                # Get active carriers associated with these shippers through carrier_shipper relationship
                active_carriers = db.session.query(Carrier)\
                    .join(carrier_shipper)\
                    .filter(
                        carrier_shipper.c.shipper_id.in_(shipper_ids),
                        Carrier.active == True
                    )\
                    .distinct()\
                    .count()

                stats.update(
                    {
                        "pending_quotes": Quote.query.filter(
                            Quote.shipper_id.in_(shipper_ids),
                            ~Quote.id.in_(excluded_quotes_subquery),
                            ~expired_condition
                        ).count(),
                        "active_shippers": len(shipper_ids),
                        "active_carriers": active_carriers,  # Carriers asociados a los shippers de la compañía
                        "active_companies": 1,
                        "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate))
                        .join(Quote)
                        .filter(
                            Quote.shipper_id.in_(shipper_ids),
                            QuoteCarrierRate.status == "accepted",
                        )
                        .scalar()
                        or 0,
                        "completedQuotes": db.session.query(QuoteCarrierRate)
                        .join(Quote)
                        .filter(
                            Quote.shipper_id.in_(shipper_ids),
                            QuoteCarrierRate.status == "accepted",
                        )
                        .count(),
                    }
                )

        elif user.role == "CarrierAdmin":
            user = User.query.get(user_id)
            carrier = Carrier.query.filter(Carrier.users.any(id=user.id)).first()
            if carrier:
                stats.update(
                    {
                        "pending_quotes": db.session.query(Quote)
                        .join(quote_carrier)
                        .filter(
                            quote_carrier.c.carrier_id == carrier.id,
                            ~db.session.query(QuoteCarrierRate)
                            .filter(
                                QuoteCarrierRate.quote_id == Quote.id,
                                QuoteCarrierRate.carrier_admin_id == user_id,
                                QuoteCarrierRate.status.in_(["accepted", "declined"]),
                            )
                            .exists(),
                            ~expired_condition
                        )
                        .count(),
                        "active_shippers": db.session.query(Shipper)
                        .join(carrier_shipper)
                        .filter(
                            carrier_shipper.c.carrier_id == carrier.id,
                            Shipper.active == True,
                        )
                        .count(),
                        "active_carriers": 1,
                        "active_companies": 1,
                        "spendMT": db.session.query(func.sum(QuoteCarrierRate.rate))
                        .filter(
                            QuoteCarrierRate.carrier_admin_id == user_id,
                            QuoteCarrierRate.status == "accepted",
                        )
                        .scalar()
                        or 0,
                        "completedQuotes": QuoteCarrierRate.query.filter(
                            QuoteCarrierRate.carrier_admin_id == user_id,
                            QuoteCarrierRate.status == "accepted",
                        ).count(),
                    }
                )

        return jsonify({
            "user_name": f"{user.first_name} {user.last_name}",
            "stats": stats
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to get dashboard stats: {str(e)}"
        }), 500


@app_routes.route("/api/carrier/<int:carrier_id>/shippers", methods=["GET"])
def get_carrier_creator(carrier_id):
    # Primero verificar que el carrier existe
    user = User.query.get(carrier_id)
    carrier = Carrier.query.filter(Carrier.users.any(id=user.id)).first()
    
    if not carrier:
        return jsonify({"error": "Carrier not found"}), 404

    # Obtener todos los shippers asociados a este carrier usando la relación definida
    associated_shippers = []
    
    for shipper in carrier.shippers:  # Esto usa la relación back_populates="shippers" del modelo Carrier
        user = shipper.user  # Accediendo al usuario relacionado
        company = shipper.company  # Accediendo a la compañía relacionada
        
        shipper_data = {
            "shipper_id": shipper.id,
            "user_info": {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone
            },
            "company_info": {
                "company_id": company.id,
                "company_name": company.company_name,
                "duns_number": company.duns,
                "mc_number": company.mc_number if hasattr(company, 'mc_number') else None
            },
            "association_details": {
                "is_active": shipper.active,
                "created_at": shipper.created_at.isoformat() if shipper.created_at else None
            }
        }
        associated_shippers.append(shipper_data)

    return jsonify({
        "carrier_id": carrier.id,
        "carrier_name": carrier.carrier_name,
        "associated_shippers": associated_shippers,
        "count": len(associated_shippers)
    })


@app_routes.route("/api/quotes/filter", methods=["POST"])
def filter_quotes():
    try:
        # Get filters from request
        filters = request.get_json()
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        # Base query for pending quotes
        query = Quote.query

        # For shipper view - only their quotes
        if session.get("user_role") == "Shipper":
            shipper = Shipper.query.filter_by(user_id=user_id).first()
            if not shipper:
                return jsonify({"error": "Shipper not found"}), 404
            query = query.filter_by(shipper_id=shipper.id)

        # For carrier admin view - quotes assigned to them
        elif session.get("user_role") == "CarrierAdmin":
            carrier = Carrier.query.filter_by(user_id=user_id).first()
            if not carrier:
                return jsonify({"error": "Carrier not found"}), 404

            # Get quotes where this carrier is assigned but hasn't responded yet
            query = query.join(
                quote_carrier, Quote.id == quote_carrier.c.quote_id
            ).filter(
                quote_carrier.c.carrier_id == carrier.id,
                ~exists().where(
                    and_(
                        QuoteCarrierRate.quote_id == Quote.id,
                        QuoteCarrierRate.carrier_admin_id == user_id,
                    )
                ),
            )

        # Apply date filters
        date_start = filters.get("date_start")
        date_end = filters.get("date_end")

        if date_start:
            start_date = datetime.strptime(date_start, "%Y-%m-%d").date()
            query = query.filter(Quote.created_at >= start_date)

        if date_end:
            end_date = datetime.strptime(date_end, "%Y-%m-%d").date()
            query = query.filter(Quote.created_at <= end_date)

        # Apply lane filter (origin → destination)
        lane = filters.get("lane")
        if lane:
            origin, destination = map(str.strip, lane.split("→"))
            query = query.filter(
                Quote.origin.ilike(f"%{origin}%"),
                Quote.destination.ilike(f"%{destination}%"),
            )

        # Apply equipment filter
        equipment = filters.get("equipment")
        if equipment:
            query = query.filter_by(equipment_type=equipment)

        # Apply carrier filter (only for shipper view)
        carrier_filter = filters.get("carrier")
        if carrier_filter and session.get("user_role") == "Shipper":
            if carrier_filter == "none":
                # Quotes with no accepted carrier
                query = query.filter(Quote.accepted_carrier_admin.is_(None))
            else:
                # Quotes with specific accepted carrier
                query = query.filter(
                    Quote.accepted_carrier_admin.ilike(f"%{carrier_filter}%")
                )

        # Get only pending quotes (not accepted or declined by all carriers)
        if session.get("user_role") == "Shipper":
            # For shipper - quotes that still have carriers who haven't responded
            subquery = (
                db.session.query(
                    QuoteCarrierRate.quote_id,
                    func.count(QuoteCarrierRate.id).label("response_count"),
                )
                .group_by(QuoteCarrierRate.quote_id)
                .subquery()
            )

            query = query.outerjoin(subquery, Quote.id == subquery.c.quote_id).filter(
                or_(
                    subquery.c.response_count.is_(None),
                    subquery.c.response_count < func.array_length(Quote.carriers, 1),
                )
            )

        # Execute query
        quotes = query.order_by(Quote.created_at.desc()).all()

        # Serialize results
        result = []
        for quote in quotes:
            quote_data = {
                "id": quote.id,
                "created_at": quote.created_at.isoformat(),
                "origin": quote.origin,
                "destination": quote.destination,
                "equipment_type": quote.equipment_type,
                "pickup_date": (
                    quote.pickup_date.isoformat() if quote.pickup_date else None
                ),
                "open_value": quote.open_value,
                "open_unit": quote.open_unit,
                "rates_received": len(
                    [r for r in quote.quote_rates if r.rate is not None]
                ),
                "accepted_rate": (
                    float(quote.accepted_rate) if quote.accepted_rate else None
                ),
                "accepted_carrier": quote.accepted_carrier_admin,
                "status": "Pending",  # You might have more sophisticated status logic
            }
            result.append(quote_data)

        return jsonify({"status": "success", "data": result, "count": len(result)})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
def get_user_data_for_shipper(users, shipper_id):
    user = next((u for u in users if u.shipper_id == shipper_id), None)
    if user:
        return {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "email": user.email,
            "active": user.active
        }
    return None


@app_routes.route("/api/cognito/delete_all_users", methods=["DELETE"])
def delete_all_cognito_users():
    """
    Endpoint to delete all users from a Cognito User Pool
    WARNING: This is a destructive operation and should be protected
    """
    try:
        # Initialize Cognito client
        client = boto3.client('cognito-idp', region_name=Config.COGNITO_REGION)
        
        # List all users in the pool
        users = []
        pagination_token = None
        
        while True:
            list_users_args = {
                'UserPoolId': Config.USER_POOL_ID,
                'Limit': 60  # Maximum allowed by Cognito
            }
            
            if pagination_token:
                list_users_args['PaginationToken'] = pagination_token
                
            response = client.list_users(**list_users_args)
            users.extend(response['Users'])
            
            if 'PaginationToken' not in response:
                break
                
            pagination_token = response['PaginationToken']
        
        # Delete users in batches (Cognito has rate limits)
        deleted_count = 0
        for user in users:
            try:
                username = user['Username']
                client.admin_delete_user(
                    UserPoolId=Config.USER_POOL_ID,
                    Username=username
                )
                deleted_count += 1
                # Small delay to avoid hitting rate limits
                time.sleep(0.1)
            except Exception as e:
                print(f"Error deleting user {username}: {str(e)}")
                continue
        
        return jsonify({
            "status": "success",
            "message": f"Deleted {deleted_count} users from Cognito User Pool",
            "total_users": len(users)
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to delete users: {str(e)}"
        }), 500
