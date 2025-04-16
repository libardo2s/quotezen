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
    carrier = Carrier.query.filter_by(user_id=user_id).first()
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
    f = Fernet(Config.HASH_KEY)
    encrypted_email = f.encrypt(data["contact_email"].encode()).decode()

    # Send the hashed email via POST
    register_url = f"{Config.DOMAIN_URL}/complete-registration/{encrypted_email}"

    if not shipper:
        return jsonify({"success": False, "message": "Shipper not found"}), 404
    try:
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

    except IntegrityError as e:
        db.session.rollback()
        if isinstance(e.orig, UniqueViolation):
            # Check which constraint was violated
            if 'scac' in str(e.orig):
                return jsonify({
                    "status": "error",
                    "message": "A carrier with this SCAC code already exists"
                }), 400
            elif 'mc_number' in str(e.orig):
                return jsonify({
                    "status": "error",
                    "message": "A carrier with this MC number already exists"
                }), 400
            elif 'email' in str(e.orig):
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
            "message": str(e),
        }), 400

    try:
        html_content = render_template(
            "email/carrier_welcome_email.html",
            shipper_name=f"{shipper.user.first_name} {shipper.user.last_name}",
            contact_name=data["carrier_name"],
            invite_url=register_url,
            current_year=datetime.utcnow().year
        )
        print(html_content)

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
            "message": "Carrier Admin created",
            "complete_registration": register_url
        }), 200