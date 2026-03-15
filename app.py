from datetime import time

from flask import Flask, render_template, request, redirect, url_for, session, jsonify,flash
import firebase_admin
from firebase_admin import credentials, db, storage, auth
import uuid
import os
from werkzeug.security import generate_password_hash, check_password_hash
import yagmail
import datetime  # Importing datetime module
# Simulated database
plumbing_users = []
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
yag = yagmail.SMTP('windturbinefall2024@gmail.com', 'levmtkpvgafjcsic')
# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("handypro-63ade-firebase-adminsdk-8vcea-e42dd9b827.json")  # Replace with your Firebase credentials JSON file
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'handypro-63ade.appspot.com',  # Replace with your Firebase Storage bucket name
        'databaseURL': 'https://handypro-63ade-default-rtdb.firebaseio.com'  # Replace with your Realtime Database URL
    })
bucket = storage.bucket()
ADMIN_EMAIL = 'admin@gmail.com'
ADMIN_PASSWORD = '123456789'

# Define routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Fetch all user data from Firebase Realtime Database
        users_ref = db.reference('users')
        users = users_ref.get()

        # Check each user for matching email and approved status
        for user_id, user_data in users.items():
            if user_data['email'] == email:
                # Check if user is approved
                if user_data.get('approved', False):
                    # Verify hashed password
                    if check_password_hash(user_data['password'], password):
                        # Store user data in session
                        session['user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email'],
                            'image_url': user_data.get('image_url', '')
                        }
                        # Redirect to worker dashboard
                        return redirect(url_for('worker_dashboard'))
                    else:
                        # Invalid password
                        return render_template("login.html", error="Invalid password.")
                else:
                    # User not approved
                    return render_template("login.html", error="Your account is not yet approved. Please wait.")

        # If no user is found with the provided email
        return render_template("login.html", error="Invalid email or account not found.")

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    # POST method to handle form submission
    data = request.form
    print(data)
    email = data.get('email')
    print(email)
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    name = data.get('name')
    address = data.get('address')
    contact_details = data.get('contact_details')
    nic_number = data.get('nic_number')
    experience = data.get('experience')
    education = data.get('education')
    skills = data.getlist('skills')  # Multiple skills can be selected
    references = data.get('references')
    availability = data.get('availability')
    image_file = request.files['image']

    # Validate password
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400
    if len(password) < 8 or '@' not in password:
        return jsonify({"error": "Password must be at least 8 characters and include an '@' symbol"}), 400

    # Hash password
    hashed_password = generate_password_hash(password)

    # Save image locally and store the path
    try:
        image_filename = f"{uuid.uuid4()}-{image_file.filename}"
        image_path = os.path.join('static/images/uploads', image_filename)
        if not os.path.exists('static/images/uploads'):
            os.makedirs('static/images/uploads')
        image_file.save(image_path)
        image_url = f"/{image_path}"  # URL to access image

    except Exception as e:
        return jsonify({"error": f"Image upload failed: {str(e)}"}), 500

    try:
        # Create user in Firebase Authentication
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )

        # Add user details to Firebase Realtime Database
        user_ref = db.reference(f'users/{user_record.uid}')

        user_ref.set({
            'name': name,
            'email': email,
            'address': address,
            'contact_details': contact_details,
            'nic_number': nic_number,
            'experience': experience,
            'education': education,
            'skills': skills,
            'references': references,
            'availability': availability,
            'approved': False,
            'image_url': image_url,  # Path to local image
            'password': hashed_password
        })

        return jsonify({"message": "User created successfully. Awaiting admin approval."}), 201
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/worker_dashboard')
def worker_dashboard():
    # Check if the user is logged in
    if 'user' not in session:
        # Redirect to login if user data is not in session
        return redirect(url_for('login'))

    # Retrieve user information from session
    # Retrieve user information from session
    user = session['user']
    return render_template('worker_dashboard.html', user=user)
@app.route('/api/update_status/<user_id>', methods=['POST'])
def update_status(user_id):
    status = request.json.get('status')
    try:
        # Update the user's status in the Firebase Realtime Database
        db.reference(f'plumbing_users/{user_id}').update({
            'status': status
        })
        return jsonify({"message": "Status updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to update status: {str(e)}"}), 500


@app.route('/admin')
def admin_panel():
    return render_template('admin.html')


@app.route('/admin/requests', methods=['GET'])
def get_pending_requests():
    try:
        user_types = ['appliance_users', 'carpentry_users', 'cleaning_users', 'hvac_users', 'plumbing_users',
                      'electrical_users']
        pending_users = []

        for user_type in user_types:
            users_ref = db.reference(user_type)

            all_users = users_ref.get() or {}

            for user_id, user_data in all_users.items():
                if not user_data.get('approved', False):
                    pending_users.append({"id": user_id, "type": user_type, **user_data})

        return jsonify(pending_users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/user/<user_type>/<user_id>', methods=['GET'])
def get_user_details(user_type, user_id):
    try:
        user_ref = db.reference(f'{user_type}/{user_id}')
        user_data = user_ref.get()

        if not user_data:
            return jsonify({"error": f"User not found in {user_type}"}), 404

        return jsonify(user_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/approve', methods=['POST'])
def approve_user():
    user_id = request.json.get('user_id')
    user_type = request.json.get('user_type')

    if not user_id or not user_type:
        return jsonify({"error": "User ID and User Type are required."}), 400

    try:
        user_ref = db.reference(f'{user_type}/{user_id}')
        user_data = user_ref.get()

        if not user_data:
            return jsonify({"error": f"User not found in {user_type}"}), 404

        user_ref.update({'approved': True, 'status': 'Online'})
        yag.send(user_data['email'], 'Account Approved',
                 'Congratulations! Your account has been approved and is now online.')

        return jsonify({"message": "User approved and set to online successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/reject', methods=['POST'])
def reject_user():
    user_id = request.json.get('user_id')
    user_type = request.json.get('user_type')

    if not user_id or not user_type:
        return jsonify({"error": "User ID and User Type are required."}), 400

    try:
        user_ref = db.reference(f'{user_type}/{user_id}')
        user_data = user_ref.get()

        if not user_data:
            return jsonify({"error": f"User not found in {user_type}"}), 404

        user_ref.delete()
        yag.send(user_data['email'], 'Account Rejected', 'We regret to inform you that your account was not approved.')

        return jsonify({"message": "User rejected successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/active_workers', methods=['GET'])
def get_active_workers():
    try:
        user_types = ['appliance_users', 'carpentry_users', 'cleaning_users', 'hvac_users', 'plumbing_users',
                      'electrical_users']
        active_workers = []

        for user_type in user_types:
            users_ref = db.reference(user_type)
            all_users = users_ref.get() or {}

            for user_id, user_data in all_users.items():
                if user_data.get('approved', False) and user_data.get('status', '') == 'Online':
                    active_workers.append({"id": user_id, "type": user_type, **user_data})

        return jsonify(active_workers), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#-----------------------------------------------------------------------------------------------------------
# Route to render the wind turbine status page
@app.route('/windturbine_status')
def windturbine_status():
    return render_template('windturbine_status.html')

# Route to get the list of wind turbines
@app.route('/windturbine/list', methods=['GET'])
def list_windturbines():
    try:
        turbines_ref = db.reference('data/windturbine')
        turbines = turbines_ref.get()

        if turbines is None:
            return jsonify({"error": "No turbines found"}), 404

        # Return the list of turbine data
        return jsonify(turbines), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to get details of a specific wind turbine
@app.route('/windturbine/<turbine_id>', methods=['GET'])
def get_windturbine_details(turbine_id):
    try:
        # Fetch the specific turbine details from the correct path in the Firebase database
        turbine_ref = db.reference(f'data/windturbine/{turbine_id}')
        turbine_data = turbine_ref.get()

        if turbine_data is None:
            return jsonify({"error": "Turbine not found"}), 404

        # Return the turbine data
        return jsonify(turbine_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#---------------------turbine save values-------------------------------------
@app.route('/save_turbine_data', methods=['POST'])
def save_turbine_data():
    # Get the data from the request
    data = request.json
    if not data or 'turbineId' not in data or 'data' not in data:
        return jsonify({"error": "Invalid data"}), 400

    # Simulate saving data
    global saved_data
    saved_data.extend(data['data'])
    print(f"Data saved for turbine {data['turbineId']} at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Return a success response
    return jsonify({"message": "Data saved successfully"}), 200

@app.route('/get_turbine_data', methods=['GET'])
def get_turbine_data():
    # Return all the saved data
    return jsonify(saved_data), 200

@app.route('/clear_data', methods=['POST'])
def clear_data():
    # Clear the saved data
    global saved_data
    saved_data = []
    return jsonify({"message": "Data cleared successfully"}), 200

# Admin login route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if the credentials match the hardcoded admin credentials
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Successfully logged in as admin', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('admin_login'))

    # Render the admin login page
    return render_template('admin_login.html')

# Admin dashboard route
@app.route('/admin/dashboard')
def admin_dashboard():
    # Check if the admin is logged in
    if not session.get('admin_logged_in'):
        flash('Please log in to access the admin dashboard', 'warning')
        return redirect(url_for('admin_login'))

    # Render the admin.html page
    return render_template('admin.html')

@app.route('/admin/online_workers', methods=['GET'])
def online_workers():
    try:
        # Reference to the 'users' node in the Firebase Realtime Database
        users_ref = db.reference('users')
        all_users = users_ref.get()

        if not all_users:
            flash("No users found in the database.", "warning")
            return redirect(url_for('admin_panel'))

        # Filter users who have the status 'online'
        online_users = [
            {"uid": uid, "name": user_data.get("name", "N/A"), "email": user_data.get("email", "N/A"),
             "contact_details": user_data.get("contact_details", "N/A"), "status": user_data.get("status", "offline")}
            for uid, user_data in all_users.items()
            if user_data.get('status') == 'Online'
        ]

        # Render the online_workers.html template with the filtered online users
        return render_template('online_workers.html', online_users=online_users)
    except Exception as e:
        flash(f"Error fetching online workers: {str(e)}", "danger")
        return redirect(url_for('admin_panel'))

# Admin logout route
@app.route('/admin/logout')
def admin_logout():
    # Log out the admin
    session.pop('admin_logged_in', None)
    flash('Successfully logged out', 'success')
    return redirect(url_for('admin_login'))



# ------------------------------------------
# 🔹 RENDER SIGNUP FORM
# ------------------------------------------
@app.route('/plumbing_signup', methods=['GET'])
def plumbing_signup_form():
    return render_template('plumbing_signup.html')

# ------------------------------------------
# 🔹 HANDLE SIGNUP FORM SUBMISSION
# ------------------------------------------
@app.route('/plumbing_signup', methods=['POST'])
def plumbing_signup():
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        contact_details = request.form.get('contact_details', '').strip()
        experience = request.form.get('experience', '').strip()
        skills = request.form.getlist('skills')  # List of selected skills
        certifications = request.form.get('certifications', '').strip()
        references = request.form.get('references', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        image = request.files.get('image')

        # Validate required fields
        if not all([name, email, address, contact_details, experience, certifications, references, password]):
            return jsonify({'error': 'All fields are required'}), 400

        # Validate password and confirmation match
        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400

        # Hash the password securely
        hashed_password = generate_password_hash(password)

        # Handle image upload (Save locally)
        image_url = None
        if image:
            image_filename = f"{uuid.uuid4()}_{image.filename}"
            image_path = os.path.join('static/uploads', image_filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            image_url = f"/{image_path}"  # Store the local file path as the URL

        # Create user in Firebase Authentication
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=name
        )

        # Save user data to Firebase Realtime Database
        user_ref = db.reference(f'plumbing_users/{user_record.uid}')
        user_ref.set({
            'name': name,
            'email': email,
            'address': address,
            'contact_details': contact_details,
            'experience': experience,
            'skills': skills,
            'certifications': certifications,
            'references': references,
            'approved': False,  # Default is pending approval
            'image_url': image_url,  # Path to locally saved image
            'password': hashed_password
        })

        return jsonify({'message': 'Registration successful! Awaiting admin approval.'}), 201

    except Exception as e:
        print(f"Signup Error: {e}")  # Debugging Log
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# ------------------------------------------
# 🔹 HANDLE LOGIN FORM
# ------------------------------------------
@app.route('/plumbing_login', methods=['GET'])
def plumbing_login_form():
    return render_template('plumbing_login.html')

@app.route('/plumbing_login', methods=['GET', 'POST'])
def plumbing_login():
    if request.method == 'GET':
        return render_template('plumbing_login.html')

    elif request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template("plumbing_login.html", error="Email and password are required.")

        try:
            # Retrieve all plumbing users from Firebase
            users_ref = db.reference('plumbing_users')
            users = users_ref.get() or {}  # Ensure it doesn't return None

            # Check if user exists
            for user_id, user_data in users.items():
                if user_data.get('email') == email:
                    # Check if the account is approved
                    if not user_data.get('approved', False):
                        return render_template("plumbing_login.html", error="Your account is not yet approved. Please wait.")

                    # Verify the hashed password
                    stored_password = user_data.get('password', '')
                    if stored_password and check_password_hash(stored_password, password):
                        # Store user details in session
                        session['plumbing_user'] = {
                            'id': user_id,
                            'name': user_data.get('name', 'Unknown'),
                            'email': user_data.get('email'),
                            'image_url': user_data.get('image_url', 'https://via.placeholder.com/80')
                        }
                        return redirect(url_for('plumbing_dashboard'))  # Ensure this route exists

                    else:
                        return render_template("plumbing_login.html", error="Invalid password. Please try again.")

            # If no matching email found
            return render_template("plumbing_login.html", error="Invalid email or account not found.")

        except Exception as e:
            print(f"Error during login: {e}")  # Debugging Log
            return render_template("plumbing_login.html", error="An error occurred. Please try again later.")

@app.route('/plumbing_dashboard')
def plumbing_dashboard():
    if 'plumbing_user' not in session:
        return redirect(url_for('plumbing_login'))

    user = session['plumbing_user']
    return render_template('plumbing_dashboard.html', user=user)

# ------------------------------------------
# 🔹 LOGOUT
# ------------------------------------------
@app.route('/plumbing_logout')
def plumbing_logout():
    session.pop('plumbing_user', None)
    return redirect(url_for('plumbing_login'))
#------------------------------------------------------------Carpentry Services---------
#-----------------------------------------------------------------------------------------------------------
@app.route('/carp')
def carp():
    return render_template('carpentry_signup.html')

# Route to render the carpentry signup form and process form submissions
@app.route('/carpentry_signup', methods=['GET', 'POST'])
def carpentry_signup():
    if request.method == 'GET':
        return render_template('carpentry_signup.html')

    elif request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            address = request.form.get('address')
            contact_details = request.form.get('contact_details')
            experience = request.form.get('experience')
            skills = request.form.getlist('skills')
            certifications = request.form.get('certifications')
            references = request.form.get('references')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            image = request.files.get('image')

            if not all([name, email, address, contact_details, experience, certifications, references, password]):
                return jsonify({'error': 'All fields are required'}), 400

            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400

            hashed_password = generate_password_hash(password)

            image_url = None
            if image:
                image_filename = f"{uuid.uuid4()}_{image.filename}"
                image_path = os.path.join('static/uploads', image_filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image.save(image_path)
                image_url = f"/{image_path}"

            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )

            user_ref = db.reference(f'carpentry_users/{user_record.uid}')
            user_ref.set({
                'name': name,
                'email': email,
                'address': address,
                'contact_details': contact_details,
                'experience': experience,
                'skills': skills,
                'certifications': certifications,
                'references': references,
                'approved': False,
                'image_url': image_url,
                'password': hashed_password
            })

            return jsonify({'message': 'Registration successful! Awaiting admin approval.'}), 201

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/carpentry_login', methods=['GET', 'POST'])
def carpentry_login():
    if request.method == 'GET':
        return render_template('carpentry_login.html')

    elif request.method == 'POST':
        # If using JSON from frontend, use request.json
        data = request.json
        email = data.get('email')
        password = data.get('password')

        try:
            users_ref = db.reference('carpentry_users')
            users = users_ref.get()

            if not users:
                return jsonify({'error': 'No users found in the database.'}), 404

            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    if not user_data.get('approved', False):
                        return jsonify({'error': 'Your account is not yet approved. Please wait.'}), 403

                    # Verify password using check_password_hash
                    if check_password_hash(user_data['password'], password):
                        session['carpentry_user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email'],
                            'image_url': user_data.get('image_url', '')
                        }
                        return jsonify({'message': 'Login successful!'}), 200
                    else:
                        return jsonify({'error': 'Invalid password.'}), 401

            return jsonify({'error': 'Invalid email or account not found.'}), 404

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Route to handle carpentry dashboard
@app.route('/carpentry_dashboard')
def carpentry_dashboard():
    if 'carpentry_user' not in session:
        return redirect(url_for('carpentry_login'))

    user = session['carpentry_user']
    return render_template('carpentry_dashboard.html', user=user)

# Route to handle carpentry logout
@app.route('/carpentry_logout')
def carpentry_logout():
    session.pop('carpentry_user', None)
    return redirect(url_for('carpentry_login'))
#--------------------------------------------------House Clean
#-----------------------------------------------------------------------------------------------------------
@app.route('/clean')
def clean():
    return render_template('cleaning_signup.html')

# Route to render the cleaning signup form and process form submissions
@app.route('/cleaning_signup', methods=['GET', 'POST'])
def cleaning_signup():
    if request.method == 'GET':
        return render_template('cleaning_signup.html')

    elif request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            address = request.form.get('address')
            contact_details = request.form.get('contact_details')
            experience = request.form.get('experience')
            skills = request.form.getlist('skills')
            certifications = request.form.get('certifications')
            references = request.form.get('references')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            image = request.files.get('image')

            if not all([name, email, address, contact_details, experience, certifications, references, password]):
                return jsonify({'error': 'All fields are required'}), 400

            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400

            hashed_password = generate_password_hash(password)

            image_url = None
            if image:
                image_filename = f"{uuid.uuid4()}_{image.filename}"
                image_path = os.path.join('static/uploads', image_filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image.save(image_path)
                image_url = f"/{image_path}"

            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )

            user_ref = db.reference(f'cleaning_users/{user_record.uid}')
            user_ref.set({
                'name': name,
                'email': email,
                'address': address,
                'contact_details': contact_details,
                'experience': experience,
                'skills': skills,
                'certifications': certifications,
                'references': references,
                'approved': False,
                'image_url': image_url,
                'password': hashed_password
            })

            return jsonify({'message': 'Registration successful! Awaiting admin approval.'}), 201

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/cleaning_login', methods=['GET', 'POST'])
def cleaning_login():
    if request.method == 'GET':
        return render_template('cleaning_login.html')

    elif request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')

        try:
            users_ref = db.reference('cleaning_users')
            users = users_ref.get()

            if not users:
                return jsonify({'error': 'No users found in the database.'}), 404

            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    if not user_data.get('approved', False):
                        return jsonify({'error': 'Your account is not yet approved. Please wait.'}), 403

                    if check_password_hash(user_data['password'], password):
                        session['cleaning_user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email'],
                            'image_url': user_data.get('image_url', '')
                        }
                        return jsonify({'message': 'Login successful!'}), 200
                    else:
                        return jsonify({'error': 'Invalid password.'}), 401

            return jsonify({'error': 'Invalid email or account not found.'}), 404

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Route to handle cleaning dashboard
@app.route('/cleaning_dashboard')
def cleaning_dashboard():
    if 'cleaning_user' not in session:
        return redirect(url_for('cleaning_login'))

    user = session['cleaning_user']
    return render_template('cleaning_dashboard.html', user=user)

# Route to handle cleaning logout
@app.route('/cleaning_logout')
def cleaning_logout():
    session.pop('cleaning_user', None)
    return redirect(url_for('cleaning_login'))
#-----------------------------------------Appliance-------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------
@app.route('/appliance')
def appliance():
    return render_template('appliance_signup.html')

# Route to render the appliance repair signup form and process form submissions
@app.route('/appliance_signup', methods=['GET', 'POST'])
def appliance_signup():
    if request.method == 'GET':
        return render_template('appliance_signup.html')

    elif request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            address = request.form.get('address')
            contact_details = request.form.get('contact_details')
            experience = request.form.get('experience')
            skills = request.form.getlist('skills')
            certifications = request.form.get('certifications')
            references = request.form.get('references')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            image = request.files.get('image')

            if not all([name, email, address, contact_details, experience, certifications, references, password]):
                return jsonify({'error': 'All fields are required'}), 400

            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400

            hashed_password = generate_password_hash(password)

            image_url = None
            if image:
                image_filename = f"{uuid.uuid4()}_{image.filename}"
                image_path = os.path.join('static/uploads', image_filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image.save(image_path)
                image_url = f"/{image_path}"

            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )

            user_ref = db.reference(f'appliance_users/{user_record.uid}')
            user_ref.set({
                'name': name,
                'email': email,
                'address': address,
                'contact_details': contact_details,
                'experience': experience,
                'skills': skills,
                'certifications': certifications,
                'references': references,
                'approved': False,
                'image_url': image_url,
                'password': hashed_password
            })

            return jsonify({'message': 'Registration successful! Awaiting admin approval.'}), 201

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/appliance_login', methods=['GET', 'POST'])
def appliance_login():
    if request.method == 'GET':
        return render_template('appliance_login.html')

    elif request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')

        try:
            users_ref = db.reference('appliance_users')
            users = users_ref.get()

            if not users:
                return jsonify({'error': 'No users found in the database.'}), 404

            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    if not user_data.get('approved', False):
                        return jsonify({'error': 'Your account is not yet approved. Please wait.'}), 403

                    if check_password_hash(user_data['password'], password):
                        session['appliance_user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email'],
                            'image_url': user_data.get('image_url', '')
                        }
                        return jsonify({'message': 'Login successful!'}), 200
                    else:
                        return jsonify({'error': 'Invalid password.'}), 401

            return jsonify({'error': 'Invalid email or account not found.'}), 404

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Route to handle appliance repair dashboard
@app.route('/appliance_dashboard')
def appliance_dashboard():
    if 'appliance_user' not in session:
        return redirect(url_for('appliance_login'))

    user = session['appliance_user']
    return render_template('appliance_dashboard.html', user=user)

# Route to handle appliance repair logout
@app.route('/appliance_logout')
def appliance_logout():
    session.pop('appliance_user', None)
    return redirect(url_for('appliance_login'))
#-----------------------------------------------------------------HVAC-----------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------
@app.route('/hvac')
def hvac():
    return render_template('hvac_signup.html')

# Route to render the HVAC signup form and process form submissions
@app.route('/hvac_signup', methods=['GET', 'POST'])
def hvac_signup():
    if request.method == 'GET':
        return render_template('hvac_signup.html')

    elif request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            address = request.form.get('address')
            contact_details = request.form.get('contact_details')
            experience = request.form.get('experience')
            skills = request.form.getlist('skills')
            certifications = request.form.get('certifications')
            references = request.form.get('references')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            image = request.files.get('image')

            if not all([name, email, address, contact_details, experience, certifications, references, password]):
                return jsonify({'error': 'All fields are required'}), 400

            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400

            hashed_password = generate_password_hash(password)

            image_url = None
            if image:
                image_filename = f"{uuid.uuid4()}_{image.filename}"
                image_path = os.path.join('static/uploads', image_filename)
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image.save(image_path)
                image_url = f"/{image_path}"

            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )

            user_ref = db.reference(f'hvac_users/{user_record.uid}')
            user_ref.set({
                'name': name,
                'email': email,
                'address': address,
                'contact_details': contact_details,
                'experience': experience,
                'skills': skills,
                'certifications': certifications,
                'references': references,
                'approved': False,
                'image_url': image_url,
                'password': hashed_password
            })

            return jsonify({'message': 'Registration successful! Awaiting admin approval.'}), 201

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/hvac_login', methods=['GET', 'POST'])
def hvac_login():
    if request.method == 'GET':
        return render_template('hvac_login.html')

    elif request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')

        try:
            users_ref = db.reference('hvac_users')
            users = users_ref.get()

            if not users:
                return jsonify({'error': 'No users found in the database.'}), 404

            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    if not user_data.get('approved', False):
                        return jsonify({'error': 'Your account is not yet approved. Please wait.'}), 403

                    if check_password_hash(user_data['password'], password):
                        session['hvac_user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email'],
                            'image_url': user_data.get('image_url', '')
                        }
                        return jsonify({'message': 'Login successful!'}), 200
                    else:
                        return jsonify({'error': 'Invalid password.'}), 401

            return jsonify({'error': 'Invalid email or account not found.'}), 404

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Route to handle HVAC dashboard
@app.route('/hvac_dashboard')
def hvac_dashboard():
    if 'hvac_user' not in session:
        return redirect(url_for('hvac_login'))

    user = session['hvac_user']
    return render_template('hvac_dashboard.html', user=user)

# Route to handle HVAC logout
@app.route('/hvac_logout')
def hvac_logout():
    session.pop('hvac_user', None)
    return redirect(url_for('hvac_login'))

#-----------------------Forget-------------------
#-----------------------------------------------------------------------------------------------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    elif request.method == 'POST':
        user_type = request.form.get('user_type')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not all([user_type, email, new_password, confirm_password]):
            return jsonify({'error': 'All fields are required'}), 400

        if new_password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400

        try:
            user_ref = db.reference(f'{user_type}')
            users = user_ref.get()

            if not users:
                return jsonify({'error': 'No users found in the database.'}), 404

            user_found = False
            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    hashed_password = generate_password_hash(new_password)
                    user_ref.child(user_id).update({'password': hashed_password})
                    user_found = True
                    break

            if user_found:
                return jsonify({'message': 'Password updated successfully!'}), 200
            else:
                return jsonify({'error': 'Email not found in the specified user type.'}), 404

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
@app.route('/user_signup', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'GET':
        return render_template('User_signup.html')

    elif request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not all([name, email, password, confirm_password]):
                return jsonify({'error': 'All fields are required'}), 400

            if password != confirm_password:
                return jsonify({'error': 'Passwords do not match'}), 400

            hashed_password = generate_password_hash(password)

            user_id = str(uuid.uuid4())
            user_ref = db.reference(f'User_data/{user_id}')
            user_ref.set({
                'name': name,
                'email': email,
                'password': hashed_password
            })

            return jsonify({'message': 'Registration successful!'}), 201
        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/ser_login', methods=['GET', 'POST'])
def ser_login():
    if request.method == 'GET':
        return render_template('ser_login.html')

    elif request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')

            if not email or not password:
                return jsonify({'error': 'Email and Password are required.'}), 400

            users_ref = db.reference('User_data')
            users = users_ref.get() or {}

            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    if check_password_hash(user_data['password'], password):
                        session['user'] = {
                            'id': user_id,
                            'name': user_data['name'],
                            'email': user_data['email']
                        }
                        return redirect(url_for('ser_dashboard'))
                    else:
                        return jsonify({'error': 'Incorrect password.'}), 401

            return jsonify({'error': 'Email not found.'}), 404
        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/ser_dashboard')
def ser_dashboard():
    if 'user' not in session:
        return redirect(url_for('ser_login'))

    user = session['user']
    return render_template('ser_dashboard.html', user=user)


@app.route('/start_chat/<receiver_id>/<service_type>', methods=['GET', 'POST'])
def start_chat(receiver_id, service_type):
    if 'user' not in session:
        return redirect(url_for('ser_login'))

    sender_id = session['user']['id']
    chat_ref = db.reference(f'chats/{service_type}/{sender_id}_{receiver_id}')
    offers_ref = db.reference(f'offers/{service_type}')

    # Fetch Parent User Details
    service_map = {
        'appliance_users': 'appliance_users',
        'carpentry_users': 'carpentry_users',
        'cleaning_users': 'cleaning_users',
        'hvac_users': 'hvac_users',
        'plumbing_users': 'plumbing_users',
        'electrical': 'users'
    }
    parent_user_ref = db.reference(service_map[service_type])
    parent_user = parent_user_ref.child(receiver_id).get() or {}

    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            chat_ref.push({
                'sender': sender_id,
                'receiver': receiver_id,
                'message': message
            })
        return redirect(url_for('start_chat', receiver_id=receiver_id, service_type=service_type))

    chat_messages = chat_ref.get() or {}
    messages = [{'sender': msg.get('sender'), 'message': msg.get('message')} for msg in chat_messages.values() if isinstance(msg, dict)]

    # Fetch offers related to this chat
    all_offers = offers_ref.get() or {}
    offers = []
    for offer_id, offer_data in all_offers.items():
        if isinstance(offer_data, dict) and \
           ((offer_data.get('receiver_id') == sender_id and offer_data.get('sender_id') == receiver_id) or \
            (offer_data.get('receiver_id') == receiver_id and offer_data.get('sender_id') == sender_id)):
            offers.append({
                'offer_id': offer_id,
                'hours': offer_data.get('hours'),
                'rate_per_hour': offer_data.get('rate_per_hour'),
                'total_amount': offer_data.get('total_amount'),
                'is_offer': offer_data.get('is_offer', 'pending'),
                'sender_id': offer_data.get('sender_id'),
                'receiver_id': offer_data.get('receiver_id')
            })

    return render_template('chat.html', messages=messages, parent_user=parent_user, service_type=service_type, receiver_id=receiver_id, offers=offers)

@app.route('/check_offers/<service_type>', methods=['GET'])
def check_offers(service_type):
    if 'user' not in session:
        return redirect(url_for('login'))

    receiver_id = session['user']['id']
    offers_ref = db.reference(f'offers/{service_type}')
    all_offers = offers_ref.get() or {}

    offers = []
    for sender_receiver_key, offer_entries in all_offers.items():
        for offer_id, offer_data in offer_entries.items():
            if offer_data.get('receiver') == receiver_id:
                offers.append({
                    'offer_id': offer_id,
                    'sender': offer_data.get('sender'),
                    'receiver': offer_data.get('receiver'),
                    'message': offer_data.get('message'),
                    'timestamp': offer_data.get('timestamp'),
                    'is_offer': offer_data.get('is_offer')
                })

    parent_user_ref = db.reference(f'users/{receiver_id}')
    parent_user = parent_user_ref.get() or {}

    return render_template('chat.html', offers=offers, parent_user=parent_user, service_type=service_type)

@app.route('/accept_offer/<service_type>/<sender_receiver_key>/<offer_id>', methods=['POST'])
def accept_offer(service_type, sender_receiver_key, offer_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    offer_ref = db.reference(f'offers/{service_type}/{sender_receiver_key}/{offer_id}')
    offer_ref.update({'is_offer': 'accepted'})

    return redirect(url_for('check_offers', service_type=service_type))


@app.route('/reject_offer/<offer_id>/<sender_id>/<receiver_id>/<service_type>', methods=['POST'])
def reject_offer(offer_id, sender_id, receiver_id, service_type):
    if 'user' not in session:
        return redirect(url_for('ser_login'))

    offers_ref = db.reference(f'offers/{service_type}/{offer_id}')
    offer = offers_ref.get()

    if offer and offer.get('receiver_id') == session['user']['id'] and offer.get('is_offer') == 'pending':
        offers_ref.update({'is_offer': 'rejected'})

    return redirect(url_for('check_offers', receiver_id=receiver_id, service_type=service_type))

@app.route('/delete_offer/<offer_id>/<service_type>', methods=['POST'])
def delete_offer(offer_id, service_type):
    if 'user' not in session:
        return redirect(url_for('ser_login'))

    offers_ref = db.reference(f'offers/{service_type}/{offer_id}')
    offer = offers_ref.get()

    if offer and offer.get('sender_id') == session['user']['id']:
        offers_ref.delete()

    return redirect(url_for('check_offers', receiver_id=session['user']['id'], service_type=service_type))



@app.route('/get_users/<service_type>')
def get_users(service_type):
    try:
        service_map = {
            'appliance_users': 'appliance_users',
            'carpentry_users': 'carpentry_users',
            'cleaning_users': 'cleaning_users',
            'hvac_users': 'hvac_users',
            'plumbing_users': 'plumbing_users',
            'electrical': 'users'
        }

        if service_type not in service_map:
            return jsonify({'error': 'Invalid service type provided.'}), 400

        users_ref = db.reference(service_map[service_type])
        users = users_ref.get() or {}
        user_list = [{'id': uid, **info} for uid, info in users.items()]

        return jsonify(user_list), 200
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/user_logout')
def user_logout():
    session.pop('user', None)
    return redirect(url_for('ser_login'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user' not in session:
        return jsonify({'error': 'User not logged in.'}), 401

    sender_id = session['user']['id']
    receiver_id = request.form.get('receiver_id', '').strip()
    feedback_text = request.form.get('feedback', '').strip()
    rating = request.form.get('rating', '').strip()

    if not receiver_id or not feedback_text or not rating:
        return jsonify({'error': 'All fields are required.'}), 400

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be between 1 and 5.'}), 400

        feedback_id = str(uuid.uuid4())
        feedback_data = {
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'feedback': feedback_text,
            'rating': rating,
            'timestamp': datetime.datetime.now().isoformat()
        }

        # Ensure feedback is saved under the correct receiver ID path
        feedback_ref = db.reference(f'feedback/{receiver_id}/{feedback_id}')
        feedback_ref.set(feedback_data)

        return jsonify({'message': 'Feedback submitted successfully!', 'receiver_id': receiver_id}), 200

    except ValueError:
        return jsonify({'error': 'Rating must be a valid number.'}), 400
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/requests', methods=['GET', 'POST'])
def requests_login():
    if request.method == 'GET':
        return render_template('requests.html')

    elif request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        service_type = request.form.get('service_type')

        if not email or not password or not service_type:
            return jsonify({'error': 'All fields are required.'}), 400

        service_map = {
            'appliance_users': 'appliance_users',
            'carpentry_users': 'carpentry_users',
            'cleaning_users': 'cleaning_users',
            'hvac_users': 'hvac_users',
            'plumbing_users': 'plumbing_users',
            'electrical_users': 'users'
        }

        if service_type not in service_map:
            return jsonify({'error': 'Invalid service type.'}), 400

        users_ref = db.reference(service_map[service_type])
        users = users_ref.get() or {}

        for user_id, user_data in users.items():
            if user_data.get('email') == email:
                if check_password_hash(user_data.get('password', ''), password):
                    session['parent_id'] = user_id
                    session['service_type'] = service_type
                    return redirect(url_for('services_chat'))
                else:
                    return jsonify({'error': 'Incorrect password.'}), 401

        return jsonify({'error': 'Email not found.'}), 404


@app.route('/services_chat', methods=['GET'])
def services_chat():
    if 'parent_id' not in session:
        return redirect(url_for('requests'))

    parent_id = session['parent_id']
    service_type = session['service_type']

    chats_ref = db.reference(f'chats/{service_type}')
    all_chats = chats_ref.get() or {}

    # Extracting unique sender IDs where parent is the receiver
    unique_senders = set()
    for conversation_id, messages in all_chats.items():
        for msg_id, chat_data in messages.items():
            if chat_data.get('receiver') == parent_id:
                unique_senders.add(chat_data.get('sender'))

    # Fetch sender details from User_data
    sender_details = []
    for sender_id in unique_senders:
        user_ref = db.reference(f'User_data/{sender_id}')
        user_info = user_ref.get()
        if user_info:
            sender_details.append({
                'id': sender_id,
                'name': user_info.get('name', 'Unknown'),
                'email': user_info.get('email', 'N/A'),
                'status': user_info.get('status', 'Offline'),
                'image_url': user_info.get('image_url', '')
            })

    return render_template('services_chat.html', senders=sender_details, service_type=service_type.capitalize())


@app.route('/services_chat/<receiver_id>/<service_type>', methods=['GET', 'POST'])
def services_chat1(receiver_id, service_type):
    if 'parent_id' not in session:
        return redirect(url_for('requests'))

    parent_id = session['parent_id']
    print(parent_id)

    # Create a unique chat reference for the sender and receiver
    chat_id = f"{parent_id}_{receiver_id}"
    chat_ref = db.reference(f'chats/{service_type}/{chat_id}')

    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            chat_ref.push({
                'sender': parent_id,
                'receiver': receiver_id,
                'message': message
            })
            return redirect(url_for('services_chat', receiver_id=receiver_id, service_type=service_type))

    # Fetch chat messages to display
    chat_messages = chat_ref.get() or {}
    messages = [{'sender': msg['sender'], 'message': msg['message']} for msg in chat_messages.values()]

    return render_template('services_chat.html', messages=messages, receiver_id=receiver_id, service_type=service_type)

@app.route('/chat_box/<sender_id>', methods=['GET', 'POST'])
def chat_box(sender_id):
    if 'parent_id' not in session:
        return redirect(url_for('requests'))

    parent_id = session['parent_id']
    service_type = session['service_type']

    # Fetch user details for the chat header
    user_ref = db.reference(f'User_data/{sender_id}')
    user_details = user_ref.get() or {'name': 'Unknown', 'email': 'N/A', 'image_url': ''}

    # Chat references (for both possible directions)
    chat_ref_1 = db.reference(f'chats/{service_type}/{sender_id}_{parent_id}')
    chat_ref_2 = db.reference(f'chats/{service_type}/{parent_id}_{sender_id}')

    # Fetching existing chat data
    messages_data_1 = chat_ref_1.get() or {}
    messages_data_2 = chat_ref_2.get() or {}

    # Combine messages from both directions and sort by timestamp
    all_messages = {**messages_data_1, **messages_data_2}
    sorted_messages = sorted(all_messages.values(), key=lambda x: x.get('timestamp', ''))

    # Handle message submission (either regular message or offer)
    if request.method == 'POST':
        message = request.form.get('message')
        offer_message = request.form.get('offer_message')  # New: Handle offer message submission

        chat_data = {
            'sender': parent_id,
            'receiver': sender_id,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        }

        if message:
            chat_data['message'] = message
            chat_data['is_offer'] = False  # Regular message
        elif offer_message:
            chat_data['message'] = offer_message
            chat_data['is_offer'] = True  # Offer message

        # Save the message in the appropriate chat reference
        if messages_data_1:
            chat_ref_1.push(chat_data)
        elif messages_data_2:
            chat_ref_2.push(chat_data)
        else:
            chat_ref_1.push(chat_data)  # Create new chat if none exists

        return redirect(url_for('chat_box', sender_id=sender_id))

    return render_template('chat_box.html', messages=sorted_messages, user_details=user_details)


@app.route('/Reviews', methods=['GET'])
def reviews():
    if 'plumbing_user' not in session:
        return redirect(url_for('plumbing_login'))

    parent_id = session['plumbing_user']['id']
    print(parent_id)

    try:
        # Fetch feedback data from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}
        print(all_reviews)
        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        plumber_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                plumber_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('reviews.html', reviews=plumber_reviews, user=session['plumbing_user'])

    except Exception as e:
        print(f"Error fetching reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
@app.route('/appliance_reviews', methods=['GET'])
def appliance_reviews():
    if 'appliance_user' not in session:
        return redirect(url_for('appliance_login'))

    parent_id = session['appliance_user']['id']

    try:
        # Fetch feedback data from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}

        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        appliance_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                appliance_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('appliance_reviews.html', reviews=appliance_reviews, user=session['appliance_user'])

    except Exception as e:
        print(f"Error fetching appliance reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
@app.route('/carpentry_reviews', methods=['GET'])
def carpentry_reviews():
    if 'carpentry_user' not in session:
        return redirect(url_for('carpentry_login'))

    parent_id = session['carpentry_user']['id']

    try:
        # Fetch feedback data from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}

        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        carpentry_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                carpentry_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('carpentry_reviews.html', reviews=carpentry_reviews, user=session['carpentry_user'])

    except Exception as e:
        print(f"Error fetching carpentry reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
@app.route('/cleaning_reviews', methods=['GET'])
def cleaning_reviews():
    if 'cleaning_user' not in session:
        return redirect(url_for('cleaning_login'))

    parent_id = session['cleaning_user']['id']

    try:
        # Fetch feedback data from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}

        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        cleaning_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                cleaning_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('cleaning_reviews.html', reviews=cleaning_reviews, user=session['cleaning_user'])

    except Exception as e:
        print(f"Error fetching cleaning reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
@app.route('/hvac_reviews', methods=['GET'])
def hvac_reviews():
    if 'hvac_user' not in session:
        return redirect(url_for('hvac_login'))

    parent_id = session['hvac_user']['id']

    try:
        # Fetch feedback from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}

        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        hvac_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                hvac_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('hvac_reviews.html', reviews=hvac_reviews, user=session['hvac_user'])

    except Exception as e:
        print(f"Error fetching HVAC reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
@app.route('/electrical_reviews', methods=['GET'])
def electrical_reviews():
    if 'user' not in session:
        return redirect(url_for('ser_login'))

    parent_id = session['user']['id']

    try:
        # Fetch feedback from Firebase
        reviews_ref = db.reference(f'feedback/{parent_id}')
        all_reviews = reviews_ref.get() or {}

        # Ensure retrieved data is a dictionary
        if not isinstance(all_reviews, dict):
            all_reviews = {}

        electrical_reviews = []

        # Process each review and store it in a list
        for review_id, review_data in all_reviews.items():
            if isinstance(review_data, dict):  # Prevent int object errors
                electrical_reviews.append({
                    'reviewer': review_data.get('sender_id', 'Anonymous'),
                    'feedback': review_data.get('feedback', 'No Feedback Provided'),
                    'rating': review_data.get('rating', 0),
                    'timestamp': review_data.get('timestamp', 'N/A')
                })

        return render_template('electrical_reviews.html', reviews=electrical_reviews, user=session['user'])

    except Exception as e:
        print(f"Error fetching Electrical reviews: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
