import os
import boto3
import pandas as pd
from flask import jsonify, request
from sqlalchemy import and_, case, func, or_, text
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
    
    user_role = session.get('user_role')

    # Get most recent quotes
    recent_quotes_query = (
        db.session.query(Quote)
        .options(joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier))
        .order_by(Quote.created_at.desc())
        .limit(5)
        .all()
    )
    
    recent_quotes = []
    for quote in recent_quotes_query:
        latest_rate = sorted(quote.quote_rates, key=lambda r: r.created_at or datetime.min, reverse=True)
        awarded_rate = next((r for r in latest_rate if r.status == "accepted"), None)
        status = "Open" if not awarded_rate else "Awarded"
        if not awarded_rate and latest_rate:
            status = "Declined"

        carrier_name = awarded_rate.carrier.carrier_name if awarded_rate and awarded_rate.carrier else None

        recent_quotes.append({
            "lane": f"{quote.origin}-{quote.destination}",
            "rate": awarded_rate.rate if awarded_rate else None,
            "carrier": carrier_name,
            "benchmark": quote.benchmark_rate if hasattr(quote, "benchmark_rate") else None,
            "status": status
        })

    # Top carriers by win percentage
    carriers = Carrier.query.all()
    top_carriers = []
    for carrier in carriers:
        total_quotes = QuoteCarrierRate.query.filter_by(carrier_id=carrier.id).count()
        awards = QuoteCarrierRate.query.filter_by(carrier_id=carrier.id, status="accepted").count()
        win_percent = round((awards / total_quotes) * 100) if total_quotes > 0 else 0
        top_carriers.append({
            "name": carrier.carrier_name,
            "quotes": total_quotes,
            "awards": awards,
            "win_percent": win_percent
        })
    top_carriers = sorted(top_carriers, key=lambda c: c['win_percent'], reverse=True)[:5]

    # Requests per user (shipper requests)
    user_requests_query = (
        db.session.query(User.first_name, db.func.count(Quote.id))
        .join(Shipper, Shipper.user_id == User.id)
        .join(Quote, Quote.shipper_id == Shipper.id)
        .group_by(User.id)
        .all()
    )
    user_requests = [{"name": name, "requests": count, "total": count} for name, count in user_requests_query]

    # Quotes per month
    this_year = datetime.utcnow().year
    quotes_per_month_raw = db.session.query(
        db.func.extract('month', Quote.created_at),
        db.func.count(Quote.id)
    ).filter(
        db.func.extract('year', Quote.created_at) == this_year
    ).group_by(
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
                         quotes_per_month=quotes_per_month)


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

    print("Carrier ID:", carrier.id if carrier else "No Carrier Found")
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
    shipper = Shipper.query.filter_by(user_id=user_id).first()

    if not shipper:
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

    quotes = Quote.query.options(
        joinedload(Quote.quote_rates).joinedload(QuoteCarrierRate.carrier)
    ).filter(
        Quote.shipper_id == shipper.id,
        ~Quote.id.in_(accepted_quotes_subquery),
        ~Quote.id.in_(declined_subquery),
        expiry_condition
    ).order_by(Quote.created_at.desc()).all()

    for quote in quotes:
        grouped = {}
        for rate in sorted(quote.quote_rates, key=lambda r: r.created_at or datetime.min, reverse=True):
            if rate.carrier_id not in grouped:
                grouped[rate.carrier_id] = rate
        quote.filtered_quote_rates = list(grouped.values())

    return render_template(
        "pending_quotes.html",
        pending_quotes=quotes,
        now=now
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

    if not shipper and not carrier:
        return redirect(url_for("app_routes.signin"))

    if shipper:
        quotes = Quote.query.filter_by(shipper_id=shipper.id)\
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
                valid_quotes.append(quote)

        modes = Mode.query.all()
        equipment_types = EquipmentType.query.all()
        rate_types = RateType.query.all()
        accessorials = Accessorial.query.all()

        return render_template(
            "quote_history.html",
            quotes=valid_quotes,
            now=now,
            user_type="shipper",
            modes=modes,
            equipment_types=equipment_types,
            rate_types=rate_types,
            accessorials=accessorials
        )

    elif carrier:
        quote_rates = QuoteCarrierRate.query\
            .filter_by(carrier_id=carrier.id)\
            .options(joinedload(QuoteCarrierRate.quote).joinedload(Quote.shipper))\
            .order_by(QuoteCarrierRate.created_at.desc())\
            .all()

        processed_quotes = []
        for rate in quote_rates:
            quote = rate.quote

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

                processed_quotes.append({
                    'quote': quote,
                    'rate': rate,
                    'expiration_status': "Expired" if is_expired else "Active"
                })

        modes = Mode.query.all()
        equipment_types = EquipmentType.query.all()
        rate_types = RateType.query.all()
        accessorials = Accessorial.query.all()

        return render_template(
            "quote_history.html",
            quotes=processed_quotes,
            now=now,
            user_type="carrier",
            modes=modes,
            equipment_types=equipment_types,
            rate_types=rate_types,
            accessorials=accessorials
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