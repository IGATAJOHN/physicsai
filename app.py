from flask import Flask, render_template, request, jsonify, send_file, make_response, flash, redirect, url_for, session
import os
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import time
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson import ObjectId
import json
from flask_login import LoginManager, login_user,login_required, current_user   #, login_required, current_user, logout_user, UserMixin
# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.secret_key = os.getenv("SECRET_KEY")

# Disable CSRF protection
# csrf = CSRFProtect(app)

# Configure MongoDB connection
mongo_uri = os.getenv("MONGODB_URI")
client = MongoClient(mongo_uri)
db = client['physics']  # Use the 'physics' database
users_collection = db['users']
login_manager = LoginManager()
login_manager.init_app(app)

# Set the login view for redirecting unauthorized users
login_manager.login_view = 'login'
# OpenAI API key
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
class User:
    def __init__(self, user_data):
        self.id = str(user_data['_id'])  # Use ObjectId as a string
        self.email = user_data['email']

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

@app.route('/')
@login_required
def home():
    return render_template('home.html', user=current_user)  # Flask-Login provides `current_user`


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Render the login page
        return render_template('login.html')
    
    # Handle POST request (actual login logic)
    email = request.form.get('email')
    password = request.form.get('password')

    # Fetch the user from MongoDB
    user_data = users_collection.find_one({"email": email})
    if not user_data:
        return jsonify({"error": "Invalid email or password"}), 401

    # Verify the password
    if not check_password_hash(user_data['password'], password):
        return jsonify({"error": "Invalid email or password"}), 401

    # Log the user in
    user = User(user_data)
    login_user(user)

    return jsonify({"message": "Login successful", "redirect": url_for('home')}), 200



class JSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder for MongoDB ObjectId."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

app.json_encoder = JSONEncoder

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')

        # Validate form input
        errors = {}
        if not first_name:
            errors['firstName'] = 'First name is required.'
        if not last_name:
            errors['lastName'] = 'Last name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        if not phone:
            errors['phone'] = 'Phone number is required.'
        if not password:
            errors['password'] = 'Password is required.'
        if password != confirm_password:
            errors['confirmPassword'] = 'Passwords do not match.'

        if errors:
            return jsonify({"error": errors}), 400

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'password': hashed_password,
            'uploads': 0  # Initialize uploads count
        }

        try:
            users_collection.insert_one(new_user)
            flash('Registration successful!', 'success')
            return jsonify({'message': 'Registration successful'}), 200
        except Exception as e:
            return jsonify({'error': 'An unexpected error occurred'}), 500

    return render_template('register.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear session data
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/users_list', methods=['GET'])
def users_list():
    users = list(users_collection.find({}, {'_id': 0}))
    return render_template('users.html', users=users)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        if not file:
            app.logger.error("No file uploaded")
            return jsonify({"error": "No file uploaded"}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        app.logger.info(f"File uploaded: {file_path}")

        # Ensure file is accessible
        with open(file_path, 'rb') as f:
            app.logger.info(f"Reopened file for reading: {file_path}")

        # Extract text based on file type
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            text = extract_text_from_image(file_path)
        elif filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        else:
            os.remove(file_path)
            app.logger.error("Unsupported file type")
            return jsonify({"error": "Unsupported file type"}), 400

        os.remove(file_path)
        app.logger.info(f"Text extracted: {text[:100]}...")

        # Extract and solve problems
        problems = extract_physics_problems(text)
        app.logger.info(f"Problems extracted: {problems}")

        solutions = solve_physics_problems(problems)
        app.logger.info(f"Solutions provided in LaTeX: {solutions}")

        # Return problems and LaTeX solutions
        return jsonify({"problems": problems, "solutions": solutions})

    except MemoryError as me:
        app.logger.error(f"Memory error: {me}")
        return jsonify({"error": "Server out of memory"}), 500

    except Exception as e:
        app.logger.error(f"Error processing file: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/download-solutions-pdf', methods=['POST'])
def download_solutions_pdf():
    try:
        solutions = request.json.get('solutions', [])
        if not solutions:
            raise ValueError("No solutions provided")

        # Generate PDF content
        pdf_content = generate_pdf_content(solutions)

        # Create a BytesIO buffer to hold the PDF data
        pdf_buffer = io.BytesIO()
        pdf_buffer.write(pdf_content)
        pdf_buffer.seek(0)

        # Create a response with the PDF data
        response = make_response(send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='solutions.pdf'))
        response.headers['Content-Disposition'] = 'attachment; filename=solutions.pdf'
        return response
    except Exception as e:
        app.logger.error(f"Error generating PDF: {e}")
        return "Internal Server Error", 500
@app.route('/confirm-upgrade', methods=['POST'])
def confirm_upgrade():
    try:
        data = request.json
        tx_ref = data.get('tx_ref')
        
        # Here you would verify the payment status with Flutterwave API
        # For example, you can use the tx_ref to check the transaction status
        # If successful, upgrade the user account in the database

        app.logger.info(f"Payment confirmed for transaction reference: {tx_ref}")
        return jsonify({"success": True, "message": "Account upgraded successfully"})
    except Exception as e:
        app.logger.error(f"Error confirming payment: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500



def generate_pdf_content(solutions):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Solutions:", styles['Title']))
    elements.append(Spacer(1, 12))

    for solution in solutions:
        # Render LaTeX content as an image using matplotlib
        fig, ax = plt.subplots(figsize=(8, 2))  # Adjust the figsize as needed
        ax.text(0.5, 0.5, f"${solution}$", fontsize=12, ha='center', va='center', wrap=True)
        ax.axis('off')

        # Save the figure to a BytesIO buffer
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight')
        plt.close(fig)
        img_buffer.seek(0)

        # Add the image to the PDF, resizing it to fit within the margins
        img = Image(img_buffer)
        img.drawWidth = 6.5 * 72  # 6.5 inches
        img.drawHeight = 2 * 72  # 2 inches
        elements.append(img)
        elements.append(Spacer(1, 12))  # Add space between solutions

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
@app.route('/users', methods=['GET'])
def users():
    try:
        # Fetch all users from the database
        users = list(users_collection.find({}, {'_id': 0, 'password': 0}))  # Exclude sensitive fields like '_id' and 'password'
        return jsonify(users), 200
    except Exception as e:
        # logging.error(f"Error fetching users: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

def extract_text_from_image(image_path):
    """Extract text from an image using Tesseract OCR."""
    image = Image.open(image_path)
    return pytesseract.image_to_string(image)

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF using PyMuPDF."""
    text = ""
    pdf_document = fitz.open(pdf_path)
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text += page.get_text()
    return text

def extract_physics_problems(text):
    """Use GPT to identify and extract questions from the text."""
    prompt = f"""
    The following text contains a physics assignment. Extract each individual question clearly and concisely:

    {text}

    List the questions one by one.
    """
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that processes text to extract questions."},
            {"role": "user", "content": prompt}
        ]
    )
    questions = response.choices[0].message.content.strip().split("\n")
    return [q.strip() for q in questions if q.strip()]

def solve_physics_problems(problems):
    """Use GPT to solve physics problems and provide step-by-step solutions in LaTeX."""
    solutions = []
    for problem in problems:
        prompt = f"""
        Solve the following physics problem and provide a detailed solution in LaTeX format. 
        The solution should include the necessary formulas, steps, and final answer, all written clearly in LaTeX.

        Problem:
        {problem}

        Ensure that the solution is concise and avoids generating multiple variations.
        """
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a physics expert providing detailed solutions in LaTeX format."},
                {"role": "user", "content": prompt}
            ]
        )
        solution = response.choices[0].message.content.strip()
        solutions.append(solution)
    return solutions

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=5000)
