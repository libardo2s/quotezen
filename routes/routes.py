import os
import boto3
import pandas as pd
from flask import jsonify, render_template, request, redirect, url_for, flash, session, render_template_string
from routes import app_routes
from cryptography.fernet import Fernet
from config import Config
from models import User, Mode, EquipmentType, RateType, Accessorial, City

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

    return render_template("dashboard.html")


@app_routes.route("/admin_settings", methods=["GET"])
def admin_settings():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    return render_template("admin_settings.html")

@app_routes.route("/carrier_network", methods=["GET"])
def carrier_network():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    return render_template("carrier_network.html")


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
    return render_template("pending_quotes.html")


@app_routes.route("/frequent_lanes", methods=["GET"])
def frequent_lanes():
    if "access_token" not in session:
        return redirect(url_for("app_routes.signin"))
    modes = Mode.query.all()
    equipment_types = EquipmentType.query.all()
    rate_types = RateType.query.all()
    accessorials = Accessorial.query.all()
    #cities = City.query.all()
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
