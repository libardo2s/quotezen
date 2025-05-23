import os
import boto3
import pandas as pd
from flask import jsonify, request
from sqlalchemy import and_, case, func, or_, text
from app.models.company import Company
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
from itsdangerous import URLSafeTimedSerializer
from app.models.association import carrier_shipper

base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, '..', 'static', 'address_info.csv')
location_df = pd.read_csv(csv_path, low_memory=False)

serializer = URLSafeTimedSerializer(Config.SECRET_KEY)


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

        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            contact_phone=contact_phone
        )
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

        user = User.query.filter_by(email=username).first()
        if not user:
            return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404

        user.active = True
        
        # Buscar y activar cualquier carrier asociado
        carrier = Carrier.query.filter(
            Carrier.users.any(id=user.id),
            Carrier.deleted == False
        ).first()

        if carrier:
            carrier.active = True
            carrier.updated_at = datetime.utcnow()
        
        db.session.commit()

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
    
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    
    # Base queries
    quote_query = db.session.query(Quote)
    quote_rate_query = db.session.query(QuoteCarrierRate)
    
    # Apply filters based on user role
    if user_role == "Shipper":
        # [Previous shipper code remains the same]
        pass
    elif user_role == "CarrierAdmin":
        # Get the current user
        current_user = User.query.get(user_id)
        if not current_user or not current_user.carrier_id:
            return redirect(url_for("app_routes.signout"))
        
        # Get the carrier through the user relationship
        carrier = current_user.carrier
        if not carrier:
            return redirect(url_for("app_routes.signout"))
        
        # Filter quote rates by this carrier
        quote_rate_query = quote_rate_query.filter(QuoteCarrierRate.carrier_id == carrier.id)
        
        # For quotes, show all where this carrier was invited
        quote_query = quote_query.join(QuoteCarrierRate, QuoteCarrierRate.quote_id == Quote.id)\
                                .filter(QuoteCarrierRate.carrier_id == carrier.id)
    
    # Get most recent quotes
    recent_quotes_query = (
        quote_query
        .options(joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier))
        .order_by(Quote.created_at.desc())
        .limit(5)
        .all()
    )
    
    recent_quotes = []
    for quote in recent_quotes_query:
        if user_role == "CarrierAdmin":
            # For carrier admin, show all responses from their carrier
            carrier_rates = [r for r in quote.quote_rates if r.carrier_id == carrier.id]
            if carrier_rates:
                # Show the latest response
                latest_rate = sorted(carrier_rates, key=lambda r: r.created_at or datetime.min, reverse=True)[0]
                status = latest_rate.status.capitalize()
                rate = latest_rate.rate
            else:
                status = "No Response"
                rate = None
                
            recent_quotes.append({
                "lane": f"{quote.origin}-{quote.destination}",
                "rate": rate,
                "shipper": quote.shipper.company_name if quote.shipper else "Unknown",
                "status": status
            })
        else:
            # [Previous admin/shipper code remains the same]
            pass

    # Top carriers - for CarrierAdmin, show their own stats
    top_carriers = []
    if user_role == "CarrierAdmin":
        total_quotes = quote_rate_query.count()
        awards = quote_rate_query.filter_by(status="accepted").count()
        win_percent = round((awards / total_quotes) * 100) if total_quotes > 0 else 0
        top_carriers.append({
            "name": carrier.carrier_name,
            "quotes": total_quotes,
            "awards": awards,
            "win_percent": win_percent
        })
    
    top_carriers = sorted(top_carriers, key=lambda c: c['win_percent'], reverse=True)[:5]

    # Requests per user - for CarrierAdmin, show requests handled by their team
    user_requests = []
    if user_role == "CarrierAdmin":
        user_requests_query = (
            db.session.query(User.first_name, db.func.count(QuoteCarrierRate.id))
            .join(QuoteCarrierRate, QuoteCarrierRate.user_id == User.id)
            .filter(User.carrier_id == carrier.id)
            .group_by(User.id)
            .all()
        )
        user_requests = [{"name": name, "requests": count} for name, count in user_requests_query]

    # Quotes per month
    this_year = datetime.utcnow().year
    monthly_query = db.session.query(
        db.func.extract('month', Quote.created_at),
        db.func.count(Quote.id)
    ).filter(
        db.func.extract('year', Quote.created_at) == this_year
    )
    
    if user_role == "CarrierAdmin":
        monthly_query = monthly_query.join(QuoteCarrierRate, QuoteCarrierRate.quote_id == Quote.id)\
                                   .filter(QuoteCarrierRate.carrier_id == carrier.id)
    
    quotes_per_month_raw = monthly_query.group_by(
        db.func.extract('month', Quote.created_at)
    ).order_by(
        db.func.extract('month', Quote.created_at)
    ).all()

    quotes_per_month = [0] * 12
    for month, count in quotes_per_month_raw:
        quotes_per_month[int(month) - 1] = count

    return render_template("dashboard.html",
                         recent_quotes=recent_quotes,
                         top_carriers=top_carriers,
                         user_requests=user_requests,
                         quotes_per_month=quotes_per_month,
                         user_role=user_role)


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
    user = User.query.get(user_id)
    carrier = Carrier.query.filter(Carrier.users.contains(user)).filter(
        Carrier.active.is_(True),
    ).first()

    if not carrier:
        return redirect(url_for("app_routes.signin"))

    filters = {
        "equipment_type": request.args.get("equipment_type"),
        "mode": request.args.get("mode"),
        "rate_type": request.args.get("rate_type"),
        "origin": request.args.get("origin"),
        "destination": request.args.get("destination"),
    }

    now = datetime.utcnow()

    accepted_quotes_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
        QuoteCarrierRate.status == 'accepted'
    ).distinct().subquery()

    declined_quotes_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
        QuoteCarrierRate.status == 'declined',
        QuoteCarrierRate.carrier_id == carrier.id
    ).distinct().subquery()

    expiry_condition = or_(
        and_(Quote.open_value.is_(None), Quote.open_unit.is_(None)),
        and_(
            Quote.open_value.isnot(None),
            Quote.open_unit.isnot(None),
            case(
                (Quote.open_unit == 'minutes',
                 Quote.created_at + (Quote.open_value * text("INTERVAL '1 minute'")) > now),
                (Quote.open_unit == 'hours',
                 Quote.created_at + (Quote.open_value * text("INTERVAL '1 hour'")) > now),
                (Quote.open_unit == 'days',
                 Quote.created_at + (Quote.open_value * text("INTERVAL '1 day'")) > now),
                else_=True
            )
        )
    )

    # Obtener el shipper actual y su compañía
    shipper = Shipper.query.filter_by(user_id=user.id).first()
    if shipper:
        # Consulta para quotes del shipper actual o de shippers de la misma compañía
        query = Quote.query.join(Shipper, Quote.shipper).join(Carrier, Quote.carriers).filter(
            Carrier.id == carrier.id,
            ~Quote.id.in_(accepted_quotes_subquery),
            ~Quote.id.in_(declined_quotes_subquery),
            expiry_condition,
            or_(
                Quote.shipper_id == shipper.id,
                Shipper.company_id == shipper.company_id
            )
        )
    else:
        # Si no es shipper, mantener la consulta original
        query = Quote.query.join(Carrier, Quote.carriers).filter(
            Carrier.id == carrier.id,
            ~Quote.id.in_(accepted_quotes_subquery),
            ~Quote.id.in_(declined_quotes_subquery),
            expiry_condition
        )

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

    for quote in carrier_quotes:
        existing_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote.id,
            carrier_id=carrier.id
        ).order_by(QuoteCarrierRate.created_at.desc()).first()

        quote.submitted_rate = existing_rate.rate if existing_rate else None
        quote.submitted_comment = existing_rate.comment if existing_rate else None

    equipment_types = [row[0] for row in db.session.query(Quote.equipment_type.distinct()).all()]
    modes = [row[0] for row in db.session.query(Quote.mode.distinct()).all()]
    rate_types = [row[0] for row in db.session.query(Quote.rate_type.distinct()).all()]

    return render_template(
        "carrier_pending_quotes.html",
        pending_quotes=carrier_quotes,
        equipment_types=equipment_types,
        modes=modes,
        carrier_admin_quote=carrier,
        rate_types=rate_types,
        now=now
    )

@app_routes.route("/carrier_pending_quotes/<hashed_id>", methods=["GET"])
def carrier_pending_quotes_id(hashed_id):
    f = Fernet(Config.HASH_KEY)
    quote_id = f.decrypt(hashed_id.encode()).decode()

    user_id = session.get("user_id")
    user = User.query.get(user_id)
    carrier = user.carrier

    if not carrier:
        return redirect(url_for("app_routes.signin"))

    carrier_company_id = carrier.primary_user_id

    filters = {
        "equipment_type": request.args.get("equipment_type"),
        "mode": request.args.get("mode"),
        "rate_type": request.args.get("rate_type"),
        "origin": request.args.get("origin"),
        "destination": request.args.get("destination"),
    }

    query = Quote.query.join(Carrier, Quote.carriers).filter(Carrier.id == carrier.id)

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

    for quote in carrier_quotes:
        existing_rate = QuoteCarrierRate.query.filter_by(
            quote_id=quote.id,
            carrier_id=carrier.id
        ).order_by(QuoteCarrierRate.created_at.desc()).first()

        quote.submitted_rate = existing_rate.rate if existing_rate else None
        quote.submitted_comment = existing_rate.comment if existing_rate else ""

    equipment_types = [row[0] for row in db.session.query(Quote.equipment_type.distinct()).all()]
    modes = [row[0] for row in db.session.query(Quote.mode.distinct()).all()]
    rate_types = [row[0] for row in db.session.query(Quote.rate_type.distinct()).all()]

    return render_template(
        "carrier_pending_quotes.html",
        pending_quotes=carrier_quotes,
        equipment_types=equipment_types,
        modes=modes,
        carrier_admin_quote=carrier,
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
    
    # Check if user is a shipper
    shipper = Shipper.query.filter_by(user_id=user_id).first()
    
    # Check if user is associated with a company (either as user_id or created_by)
    company = Company.query.filter(
        (Company.user_id == user_id) | (Company.created_by == user_id)
    ).first()

    if not shipper and not company:
        return redirect(url_for("app_routes.signin"))

    accepted_quotes_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
        QuoteCarrierRate.status == 'accepted' 
    ).distinct().subquery()

    declined_subquery = db.session.query(QuoteCarrierRate.quote_id).filter(
        QuoteCarrierRate.status == 'declined'
    ).distinct().subquery()

    now = datetime.utcnow()
    
    expiry_condition = or_(
        and_(Quote.open_value.is_(None), Quote.open_unit.is_(None)),
        and_(
            Quote.open_value.isnot(None),
            Quote.open_unit.isnot(None),
            case(
                (Quote.open_unit == 'minutes', 
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 minute'")) > now),
                (Quote.open_unit == 'hours', 
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 hour'")) > now),
                (Quote.open_unit == 'days', 
                Quote.created_at + (Quote.open_value * text("INTERVAL '1 day'")) > now),
                else_=True
            )
        )
    )

    # Base query with options
    query = Quote.query.options(
        joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier),
        joinedload(Quote.shipper).joinedload(Shipper.user)  # Load shipper and user info
    ).filter(
        ~Quote.id.in_(accepted_quotes_subquery),
        ~Quote.id.in_(declined_subquery),
        expiry_condition
    ).order_by(Quote.created_at.desc())

    # Modify query based on user type
    if company:
        # Company user - see quotes from all shippers in their company
        query = query.join(Quote.shipper).filter(
            Shipper.company_id == company.id
        )
    elif shipper:
        # Regular shipper - see their own quotes AND quotes from same company shippers
        if shipper.company_id:
            # Get all shippers from the same company
            company_shippers = Shipper.query.filter_by(company_id=shipper.company_id).all()
            shipper_ids = [s.id for s in company_shippers]
            query = query.filter(Quote.shipper_id.in_(shipper_ids))
        else:
            # Shipper without company - only their own quotes
            query = query.filter(Quote.shipper_id == shipper.id)

    quotes = query.all()

    # Group rates by carrier (latest rate per carrier)
    for quote in quotes:
        grouped = {}
        for rate in sorted(quote.quote_rates, key=lambda r: r.created_at or datetime.min, reverse=True):
            if rate.carrier_id not in grouped:
                grouped[rate.carrier_id] = rate
        quote.filtered_quote_rates = list(grouped.values())
        
        # Add flag to identify if quote belongs to current shipper
        quote.is_own_quote = quote.shipper_id == shipper.id if shipper else False

    return render_template(
        "pending_quotes.html",
        pending_quotes=quotes,
        now=now,
        is_company_user=bool(company),
        current_shipper_id=shipper.id if shipper else None  # Pass current shipper ID to template
    )


@app_routes.route("/quote_history", methods=["GET"])
def quote_history():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))

    user_id = session.get("user_id")
    now = datetime.utcnow()

    shipper = Shipper.query.filter_by(user_id=user_id).first()
    user = User.query.get(user_id)
    carrier = user.carrier if user else None
    company = Company.query.filter(
        (Company.user_id == user_id) | (Company.created_by == user_id)
    ).first()

    if not shipper and not carrier and not company:
        return redirect(url_for("app_routes.signin"))

    if company:
        # Lógica para company shipper
        quotes = Quote.query.join(Shipper).filter(
            Shipper.company_id == company.id
        ).options(
            joinedload(Quote.quote_rates),
            joinedload(Quote.shipper).joinedload(Shipper.user)
        ).order_by(Quote.created_at.desc()).all()

        processed_quotes = []
        for quote in quotes:
            accepted_rate = next((r for r in quote.quote_rates if r.status == "accepted"), None)
            declined_rates = [r for r in quote.quote_rates if r.status == "declined"]

            expiration_time = quote.created_at
            if quote.open_unit == "minutes":
                expiration_time += timedelta(minutes=quote.open_value or 0)
            elif quote.open_unit == "hours":
                expiration_time += timedelta(hours=quote.open_value or 0)
            elif quote.open_unit == "days":
                expiration_time += timedelta(days=quote.open_value or 0)

            is_expired = expiration_time < now

            if accepted_rate or declined_rates or is_expired:
                # Creamos un objeto Quote con los atributos necesarios
                quote.accepted_rate = accepted_rate.rate if accepted_rate else None
                quote.accepted_carrier = accepted_rate.carrier.carrier_name if accepted_rate and accepted_rate.carrier else None
                quote.status_summary = "Accepted" if accepted_rate else "Declined" if declined_rates else "Expired"
                quote.shipper_name = f"{quote.shipper.user.first_name} {quote.shipper.user.last_name}"
                processed_quotes.append(quote)

        return render_template(
            "quote_history.html",
            quotes=processed_quotes,
            now=now,
            user_type="company_shipper",
            modes=Mode.query.all(),
            equipment_types=EquipmentType.query.all(),
            rate_types=RateType.query.all(),
            accessorials=Accessorial.query.all()
        )

    elif shipper:
        # Nueva lógica para shipper que incluye quotes de la misma compañía
        company_id = shipper.company_id
        
        # Obtener todos los shippers de la misma compañía
        company_shippers = Shipper.query.filter_by(company_id=company_id).all()
        shipper_ids = [s.id for s in company_shippers]
        
        # Consulta para obtener quotes del shipper actual o de shippers de la misma compañía
        quotes = Quote.query.filter(Quote.shipper_id.in_(shipper_ids))\
            .options(joinedload(Quote.quote_rates))\
            .order_by(Quote.created_at.desc())\
            .all()

        valid_quotes = []
        for quote in quotes:
            accepted_rate = next((r for r in quote.quote_rates if r.status == "accepted"), None)
            declined_rates = [r for r in quote.quote_rates if r.status == "declined"]

            expiration_time = quote.created_at
            if quote.open_unit == "minutes":
                expiration_time += timedelta(minutes=quote.open_value or 0)
            elif quote.open_unit == "hours":
                expiration_time += timedelta(hours=quote.open_value or 0)
            elif quote.open_unit == "days":
                expiration_time += timedelta(days=quote.open_value or 0)

            is_expired = expiration_time < now

            if accepted_rate or declined_rates or is_expired:
                quote.accepted_rate = accepted_rate.rate if accepted_rate else None
                quote.accepted_carrier = accepted_rate.carrier.carrier_name if accepted_rate and accepted_rate.carrier else None
                quote.status_summary = "Accepted" if accepted_rate else "Declined" if declined_rates else "Expired"
                
                # Agregar información del shipper para identificar si es propio o de otro
                is_own_quote = quote.shipper_id == shipper.id
                quote.shipper_info = {
                    "name": f"{quote.shipper.user.first_name} {quote.shipper.user.last_name}",
                    "is_own": is_own_quote
                }
                
                valid_quotes.append(quote)

        return render_template(
            "quote_history.html",
            quotes=valid_quotes,
            now=now,
            user_type="shipper",
            modes=Mode.query.all(),
            equipment_types=EquipmentType.query.all(),
            rate_types=RateType.query.all(),
            accessorials=Accessorial.query.all()
        )

    elif carrier:
        # Mantener código existente para carrier
        quote_rates = QuoteCarrierRate.query\
            .filter_by(carrier_id=carrier.id)\
            .options(joinedload(QuoteCarrierRate.quote).joinedload(Quote.shipper))\
            .order_by(QuoteCarrierRate.created_at.desc())\
            .all()

        processed_quotes = []
        for rate in quote_rates:
            quote = rate.quote
            quote.rate = rate  # Agregamos el rate al objeto quote

            expiration_time = quote.created_at
            if quote.open_unit == "minutes":
                expiration_time += timedelta(minutes=quote.open_value or 0)
            elif quote.open_unit == "hours":
                expiration_time += timedelta(hours=quote.open_value or 0)
            elif quote.open_unit == "days":
                expiration_time += timedelta(days=quote.open_value or 0)

            is_expired = expiration_time < now

            if rate.status in ["accepted", "declined"] or is_expired:
                quote.rate_status = rate.status
                quote.rate_value = rate.rate
                quote.expiration_status = "Expired" if is_expired else "Active"
                quote.shipper_info = f"{quote.shipper.user.first_name} {quote.shipper.user.last_name}"
                quote.quote_date = quote.created_at.strftime('%Y-%m-%d')
                processed_quotes.append(quote)

        return render_template(
            "quote_history.html",
            quotes=processed_quotes,
            now=now,
            user_type="carrier",
            modes=Mode.query.all(),
            equipment_types=EquipmentType.query.all(),
            rate_types=RateType.query.all(),
            accessorials=Accessorial.query.all()
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


@app_routes.route("/api/reset_password", methods=["POST"])
def api_reset_password():
    try:
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([token, new_password, confirm_password]):
            return jsonify({
                "status": "error",
                "message": "All fields are required"
            }), 400
            
        if new_password != confirm_password:
            return jsonify({
                "status": "error",
                "message": "Passwords do not match"
            }), 400
            
        # Verify token
        try:
            email = serializer.loads(
                token,
                salt=Config.PASSWORD_RESET_SALT,
                max_age=Config.PASSWORD_RESET_EXPIRE_HOURS*3600
            )
        except:
            return jsonify({
                "status": "error",
                "message": "Invalid or expired token"
            }), 400
            
        # Update password in Cognito
        client = boto3.client('cognito-idp', region_name=Config.COGNITO_REGION)
        
        try:
            # First initiate forgot password flow to get the reset code
            client.forgot_password(
                ClientId=Config.CLIENT_ID,
                Username=email
            )
            
            # In a real app, you would need to handle the confirmation code flow here
            # This is a simplified version that uses admin_set_user_password
            client.admin_set_user_password(
                UserPoolId=Config.USER_POOL_ID,
                Username=email,
                Password=new_password,
                Permanent=True
            )
            
            return jsonify({
                "status": "success",
                "message": "Password updated successfully"
            })
            
        except client.exceptions.InvalidPasswordException as e:
            return jsonify({
                "status": "error",
                "message": "Password does not meet requirements"
            }), 400
        except Exception as e:
            print(f"Password reset error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Failed to update password"
            }), 500
            
    except Exception as e:
        print(f"System error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500
    
@app_routes.route("/reset-password", methods=["GET"])
def reset_password_page():
    token = request.args.get('token')
    if not token:
        #flash('Invalid password reset link', 'danger')
        return redirect(url_for('app_routes.forgot_password'))
    
    try:
        # Verify the token is valid (but don't extract email yet)
        serializer.loads(token, salt=Config.PASSWORD_RESET_SALT)
        return render_template('reset_password.html', token=token)
    except:
        #flash('The reset link is invalid or has expired', 'danger')
        return redirect(url_for('app_routes.forgot_password'))