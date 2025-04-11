import os
import boto3
import pandas as pd
from flask import jsonify, request
from app.routes import app_routes
from cryptography.fernet import Fernet
from app.config import Config
from app.models import User, Mode, EquipmentType, RateType, Accessorial, Carrier
from flask import render_template, session, redirect, url_for
from datetime import timedelta
from app.models import Quote, QuoteCarrierRate, Shipper
from app.database import db
from sqlalchemy.orm import joinedload
from datetime import datetime


base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, '..', 'static', 'address_info.csv')
location_df = pd.read_csv(csv_path, low_memory=False)


@app_routes.route("/", methods=["GET"])
def home():
    return redirect(url_for("app_routes.signin"))


@app_routes.route("/signin", methods=["GET"])
def signin():
    return render_template("signin.html")


@app_routes.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        contact_phone = request.form.get('contact_phone')

        # Add logic to save to the database (SQLAlchemy)
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            contact_phone=contact_phone
        )
        #db.session.add(new_user)
        #db.session.commit()
        
        #flash('Account created successfully!', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app_routes.route('/complete-registration/<hashed_email>', methods=["GET"])
def complete_registration(hashed_email):
    try:

        f = Fernet(Config.HASH_KEY)
        original_email = f.decrypt(hashed_email.encode()).decode()

        user = User.query.filter_by(email=original_email).first()
        if not user:
            return redirect(url_for("app_routes.signin"))

        return render_template('company_complete_registration.html', email=original_email)
    except Exception as e:
        print(str(e))
        return redirect(url_for("app_routes.signin"))
    
@app_routes.route('/complete-registration', methods=["POST"])
def company_complete_registration():
    try:
        username = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username or not password or not confirm_password:
            return jsonify({
                "status": "error",
                "message": "All fields are required."
            }), 400

        if password != confirm_password:
            return jsonify({
                "status": "error",
                "message": "Passwords do not match."
            }), 400

        client = boto3.client("cognito-idp", region_name=Config.COGNITO_REGION)

        response = client.sign_up(
            ClientId=Config.CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': username
                }
            ]
        )

        client.admin_confirm_sign_up(
            UserPoolId=Config.USER_POOL_ID,
            Username=username
        )


        return jsonify({
            "status": "success",
            "message": "Registration completed successfully!",
            "redirect_url": "/signin"
        }), 200

    except client.exceptions.UsernameExistsException:
        return jsonify({
            "status": "error",
            "message": "User already exists."
        }), 409
    except client.exceptions.InvalidPasswordException as e:
        return jsonify({
            "status": "error",
            "message": f"Password policy violation: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Registration failed: {str(e)}"
        }), 500


@app_routes.route('/opt', methods=["GET", "POST"])
def otp():
    return render_template('otp.html')


@app_routes.route('/forgot-password', methods=["GET"])
def forgot_password():
    return render_template('forgot_password.html')


@app_routes.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    # if session.get('user_role') == 'CompanyShipper':
    #     return redirect(url_for("app_routes.company_shipper"))
    # if session.get('user_role') == 'Shipper':
    #     return redirect(url_for("app_routes.shipper"))
    # if session.get('user_role') == 'CarrierAdmin':
    #     return redirect(url_for("app_routes.carrier_network"))
    # if session.get('user_role') == 'Carrier':
    #     return redirect(url_for("app_routes.carrier"))
    # if session.get('user_role') == 'Admin':
    return render_template("dashboard.html")


@app_routes.route("/admin_settings", methods=["GET"])
def admin_settings():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    return render_template("admin_settings.html")


@app_routes.route("/company_shipper", methods=["GET"])
def company_shipper():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    if session.get('user_role') == 'CompanyShipper':
        return render_template("company_shipper.html")
    else:
        return redirect(url_for("app_routes.home"))


@app_routes.route("/shipper", methods=["GET"])
def shipper():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    return render_template("carrier_network.html")
    # else:
    #     return redirect(url_for("app_routes.home"))


@app_routes.route("/carrier_network", methods=["GET"])
def carrier_network():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    return render_template("carrier_network.html")


@app_routes.route("/carrier_pending_quotes", methods=["GET"])
def carrier_pending_quotes():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))

    user_id = session.get("user_id")
    carrier_user = Carrier.query.filter_by(user_id=user_id).first()

    if not carrier_user:
        return redirect(url_for("app_routes.signin"))

    # Recoger filtros de la query
    filters = {
        "equipment_type": request.args.get("equipment_type"),
        "mode": request.args.get("mode"),
        "rate_type": request.args.get("rate_type"),
        "origin": request.args.get("origin"),
        "destination": request.args.get("destination"),
    }

    # Base query - get quotes where current carrier is one of the invited carriers
    query = Quote.query.join(Carrier, Quote.carriers).filter(Carrier.id == carrier_user.id)

    # Aplicar filtros si existen
    if filters["equipment_type"]:
        query = query.filter(Quote.equipment_type == filters["equipment_type"])
    if filters["mode"]:
        query = query.filter(Quote.mode == filters["mode"])
    if filters["rate_type"]:
        query = query.filter(Quote.rate_type == filters["rate_type"])
    if filters["origin"]:
        query = query.filter(Quote.origin.ilike(f"%{filters['origin']}%"))
    if filters["destination"]:
        query = query.filter(Quote.destination.ilike(f"%{filters['destination']}%"))

    carrier_quotes = query.all()

    # Obtener rates enviados por este usuario específico
    for quote in carrier_quotes:
        print("additional_stops:", quote.additional_stops)
        existing_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote.id,
            carrier_id=carrier_user.id  # Filter by the specific carrier user, not the company
        ).order_by(QuoteCarrierRate.created_at.desc()).first()

        # Safely handle cases where no rate exists
        quote.submitted_rate = existing_rate.rate if existing_rate else None
        quote.submitted_comment = existing_rate.comment if existing_rate else None

    # Listas únicas para los select
    equipment_types = [row[0] for row in db.session.query(Quote.equipment_type.distinct()).all()]
    modes = [row[0] for row in db.session.query(Quote.mode.distinct()).all()]
    rate_types = [row[0] for row in db.session.query(Quote.rate_type.distinct()).all()]

    return render_template(
        "carrier_pending_quotes.html",
        pending_quotes=carrier_quotes,
        equipment_types=equipment_types,
        modes=modes,
        carrier_admin_quote=carrier_user,
        rate_types=rate_types,
        now=datetime.utcnow()
    )


@app_routes.route("/carrier_pending_quotes/<hashed_id>", methods=["GET"])
def carrier_pending_quotes_id(hashed_id):
    
    f = Fernet(Config.HASH_KEY)
    quote_id = f.decrypt(hashed_id.encode()).decode()

    user_id = session.get("user_id")
    carrier_user = Carrier.query.filter_by(user_id=user_id).first()
    #print("Carrier user:", carrier_user.carrier_name)

    if not carrier_user:
        return redirect(url_for("app_routes.signin"))

    # carrier_user.created_by is the ID of User table
    carrier_company_id = carrier_user.created_by

    # Recoger filtros de la query
    filters = {
        "equipment_type": request.args.get("equipment_type"),
        "mode": request.args.get("mode"),
        "rate_type": request.args.get("rate_type"),
        "origin": request.args.get("origin"),
        "destination": request.args.get("destination"),
    }

    # Base query
    query = Quote.query.join(Carrier, Quote.carriers).filter(Carrier.user_id == user_id)
    #print("Query:", len(query.all()))
    # Aplicar filtros por defecto

    # Aplicar filtros si existen
    if filters["equipment_type"]:
        query = query.filter(Quote.equipment_type == filters["equipment_type"])
    if filters["mode"]:
        query = query.filter(Quote.mode == filters["mode"])
    if filters["rate_type"]:
        query = query.filter(Quote.rate_type == filters["rate_type"])
    if filters["origin"]:
        query = query.filter(Quote.origin.ilike(f"%{filters['origin']}%"))
    if filters["destination"]:
        query = query.filter(Quote.destination.ilike(f"%{filters['destination']}%"))

    carrier_quotes = query.all()

    # Obtener rates enviados por este usuario
    for quote in carrier_quotes:
        existing_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote.id,
            carrier_admin_id=carrier_company_id
        ).order_by(QuoteCarrierRate.created_at.desc()).first()

        quote.submitted_rate = existing_rate.rate if existing_rate else None
        quote.submitted_comment = existing_rate.comment if existing_rate else ""

    # Listas únicas para los select
    equipment_types = [row[0] for row in db.session.query(Quote.equipment_type.distinct()).all()]
    modes = [row[0] for row in db.session.query(Quote.mode.distinct()).all()]
    rate_types = [row[0] for row in db.session.query(Quote.rate_type.distinct()).all()]

    print("Quote ID:", quote_id)

    return render_template(
        "carrier_pending_quotes.html",
        pending_quotes=carrier_quotes,
        equipment_types=equipment_types,
        modes=modes,
        carrier_admin_quote=carrier_user,
        carrier_company_id=carrier_company_id,
        rate_types=rate_types,
        now=datetime.utcnow(),
        quote_id=int(quote_id),
    )


@app_routes.route("/quotes", methods=["GET"])
def quotes():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    modes = Mode.query.all()
    equipment_types = EquipmentType.query.all()
    rate_types = RateType.query.all()
    accessorials = Accessorial.query.all()
    return render_template(
        "quotes.html",
        modes=modes,
        equipment_types=equipment_types,
        rate_types=rate_types,
        accessorials=accessorials
    )


@app_routes.route("/pending_quotes", methods=["GET"])
def pending_quotes():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))

    user_id = session.get("user_id")
    shipper = Shipper.query.filter_by(user_id=user_id).first()

    if not shipper:
        return redirect(url_for("app_routes.signin"))

    # Subconsulta: quotes con al menos un rate aceptado
    accepted_quotes_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
        QuoteCarrierRate.status == 'accepted'
    ).distinct().subquery()

    # Solo quotes de este shipper que NO tienen ningún rate aceptado
    quotes = Quote.query.options(
        joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier_admin)
    ).filter(
        Quote.shipper_id == shipper.id,
        ~Quote.id.in_(accepted_quotes_subquery)
    ).order_by(Quote.created_at.desc()).all()

    # Agrupar los quote_rates por carrier_admin_id (último por fecha)
    for quote in quotes:
        grouped = {}
        for rate in sorted(quote.quote_rates, key=lambda r: r.created_at or datetime.min, reverse=True):
            if rate.carrier_admin_id not in grouped:
                grouped[rate.carrier_admin_id] = rate
        quote.filtered_quote_rates = list(grouped.values())

    return render_template(
        "pending_quotes.html",
        pending_quotes=quotes,
        now=datetime.utcnow()
    )

@app_routes.route("/quote_history", methods=["GET"])
def quote_history():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))

    user_id = session.get("user_id")
    now = datetime.utcnow()

    # Obtener el shipper logueado
    shipper = Shipper.query.filter_by(user_id=user_id).first()
    if not shipper:
        return redirect(url_for("app_routes.signin"))

    # Obtener solo los quotes de este shipper
    quotes = Quote.query.filter_by(shipper_id=shipper.id)\
        .options(joinedload(Quote.quote_rates))\
        .order_by(Quote.created_at.desc())\
        .all()

    valid_quotes = []
    for quote in quotes:
        # Rate aceptado
        accepted_rate = next((r for r in quote.quote_rates if r.status == "accepted"), None)

        # Expiración
        expiration_time = quote.created_at
        if quote.open_unit == "minutes":
            expiration_time += timedelta(minutes=quote.open_value or 0)
        elif quote.open_unit == "hours":
            expiration_time += timedelta(hours=quote.open_value or 0)
        elif quote.open_unit == "days":
            expiration_time += timedelta(days=quote.open_value or 0)

        is_expired = expiration_time < now

        if accepted_rate or is_expired:
            quote.accepted_rate = accepted_rate.rate if accepted_rate else None
            quote.accepted_carrier_admin = f"{accepted_rate.user.first_name} {accepted_rate.user.last_name}" if accepted_rate else None
            valid_quotes.append(quote)

    return render_template(
        "quote_history.html",
        quotes=valid_quotes,
        now=now
    )


@app_routes.route("/frequent_lanes", methods=["GET"])
def frequent_lanes():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    modes = Mode.query.all()
    equipment_types = EquipmentType.query.all()
    rate_types = RateType.query.all()
    accessorials = Accessorial.query.all()
    return render_template(
        "frequent_lanes.html",
        modes=modes,
        equipment_types=equipment_types,
        rate_types=rate_types,
        accessorials=accessorials
    )

@app_routes.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("app_routes.signin"))
