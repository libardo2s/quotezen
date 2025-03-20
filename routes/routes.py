from flask import jsonify, render_template, request, redirect, url_for, flash
from routes import app_routes  # Import the blueprint

@app_routes.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the Flask API!"})


@app_routes.route("/signin", methods=["GET", "POST"])
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

@app_routes.route('/opt', methods=["GET", "POST"])
def otp():
    return render_template('otp.html')

@app_routes.route('/forgot-password', methods=["GET", "POST"])
def forgot_password():
    return render_template('forgot_password.html')

@app_routes.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    return render_template('dashboard.html')


