from datetime import datetime
from app.config import Config
from flask import jsonify, request, session, render_template
from app.utils.send_email import send_email
from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation
from app.models import User, Company, Shipper, Carrier, Mode, EquipmentType, RateType, Accessorial, City, Quote


def create_carrier_user(data, user_id, db):
    # Creating a carrier with a Shipper
    user = User.query.filter_by(id=user_id).first()
    carrier = Carrier.query.filter(Carrier.users.contains(user)).first()
    f = Fernet(Config.HASH_KEY)
    encrypted_email = f.encrypt(data.get("email").encode()).decode()

    # Send the hashed email via POST
    register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"
    try:
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

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 400
    print(register_url)
    try:
        html_content = render_template(
            "email/carrier_welcome_email.html",
            shipper_name=f"{carrier.user.first_name} {carrier.user.last_name}",
            contact_name=data["carrier_name"],
            invite_url=register_url,
            current_year=datetime.utcnow().year
        )

        print(html_content)

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
            "message": "Carrier created",
            "complete_registration": register_url
        }), 200

def create_carrier_admin(data, user_id, db):
    shipper = Shipper.query.filter_by(user_id=user_id).first()
    if not shipper:
        return jsonify({"success": False, "message": "Shipper not found"}), 404

    try:
        # Check if carrier already exists by SCAC or MC number
        existing_carrier = None
        if data.get("scac"):
            existing_carrier = Carrier.query.filter_by(scac=data["scac"]).first()
        if not existing_carrier and data.get("mc_number"):
            existing_carrier = Carrier.query.filter_by(mc_number=data["mc_number"]).first()

        # Check if user email already exists
        if User.query.filter_by(email=data["contact_email"]).first():
            return jsonify({
                "status": "error", 
                "message": "User with this email already exists"
            }), 400

        # Create new user
        new_user = User(
            first_name=data.get("contact_name"),
            last_name=data.get("contact_name"),
            email=data.get("contact_email"),
            phone=data.get("contact_phone"),
            role="CarrierAdmin",
            active=False,
            shipper_id=shipper.id,
        )
        db.session.add(new_user)
        db.session.flush()

        # Prepare email variables
        f = Fernet(Config.HASH_KEY)
        encrypted_email = f.encrypt(data.get("contact_email").encode()).decode()
        register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"
        
        if existing_carrier:
            # Associate user with existing carrier
            new_user.carrier_id = existing_carrier.id
            
            # Associate shipper with carrier if not already
            if shipper not in existing_carrier.shippers:
                existing_carrier.shippers.append(shipper)
            
            db.session.commit()
            
            # Send email for existing carrier
            try:
                html_content = render_template(
                    "email/carrier_welcome_email.html",
                    shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
                    contact_name=data["contact_name"],
                    invite_url=register_url,
                    current_year=datetime.utcnow().year
                )

                send_email(
                    recipient=data.get("contact_email"),
                    subject="You're invited to QuoteZen!",
                    body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                    body_html=html_content
                )
            except Exception as e:
                print(f"Email error: {str(e)}")
            
            return jsonify({
                "status": "success",
                "message": "User created and associated with existing carrier",
                "carrier_id": existing_carrier.id,
                "complete_registration": register_url
            }), 200
        else:
            # Create new carrier with user as primary
            new_carrier = Carrier(
                carrier_name=data.get("carrier_name"),
                authority=data.get("authority"),
                scac=data.get("scac"),
                mc_number=data.get("mc_number"),
                active=False,
                primary_user_id=new_user.id,
                created_by=user_id
            )
            db.session.add(new_carrier)
            db.session.flush()
            
            # Set user's carrier association
            new_user.carrier_id = new_carrier.id
            
            # Associate shipper
            new_carrier.shippers.append(shipper)
            
            db.session.commit()
            
            # Send email for new carrier
            try:
                html_content = render_template(
                    "email/carrier_welcome_email.html",
                    shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
                    contact_name=data["contact_name"],
                    invite_url=register_url,
                    current_year=datetime.utcnow().year
                )

                send_email(
                    recipient=data.get("contact_email"),
                    subject="You're invited to QuoteZen!",
                    body_text="You've been invited to QuoteZen. Click the link to complete registration.",
                    body_html=html_content
                )
            except Exception as e:
                print(f"Email error: {str(e)}")
            
            return jsonify({
                "status": "success",
                "message": "New carrier and admin user created",
                "carrier_id": new_carrier.id,
                "complete_registration": register_url
            }), 200

    except IntegrityError as e:
        db.session.rollback()
        error_msg = "Database error"
        if isinstance(e.orig, UniqueViolation):
            if 'scac' in str(e.orig):
                error_msg = "SCAC already exists"
            elif 'mc_number' in str(e.orig):
                error_msg = "MC number already exists"
        
        return jsonify({
            "status": "error",
            "message": error_msg
        }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500