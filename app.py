import os
import pandas as pd
import json
import logging
import time
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for
import google.generativeai as genai
import requests
import logging
import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vendor_categorization')

app = Flask(__name__)

# MySQL database configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'password'),
    'database': os.getenv('MYSQL_DATABASE', 'vendor_categorization'),
    'port': int(os.getenv('MYSQL_PORT', '3306'))
}

# Database connection helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except MySQLError as e:
        logger.error(f"Error connecting to MySQL database: {e}")
        raise

# Helper function to convert MySQL result to dictionary
def row_to_dict(cursor, row):
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))

# Initialize database with retry logic
def initialize_database():
    max_retries = 10
    retry_delay = 1.0  # seconds
    
    for attempt in range(max_retries):
        conn = None
        try:
            # First, try to create the database if it doesn't exist
            temp_conn = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            temp_conn.close()
            
            # Now connect to the database and create tables
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255),
                upload_date VARCHAR(50)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorized_vendors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                upload_id INT,
                vendor_name VARCHAR(255),
                original_category VARCHAR(255),
                ai_category VARCHAR(255),
                FOREIGN KEY (upload_id) REFERENCES uploads (id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendor_categories_cache (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vendor_name VARCHAR(255) UNIQUE,
                category VARCHAR(255),
                description TEXT,
                last_updated VARCHAR(50)
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database tables initialized successfully")
            return True
        except MySQLError as e:
            if "Lock wait timeout exceeded" in str(e) and attempt < max_retries - 1:
                logger.warning(f"DATABASE WARNING: Database lock timeout during initialization, retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"DATABASE ERROR: Error initializing database after {attempt+1} attempts: {e}")
                if conn:
                    conn.close()
                return False
        except Exception as e:
            logger.error(f"DATABASE ERROR: Error initializing database: {e}")
            if conn:
                conn.close()
            return False
    
    return False

# Initialize database on startup
try:
    initialize_database()
except Exception as e:
    logger.error(f"Error initializing database tables: {e}")

# Define allowed categories
ALLOWED_CATEGORIES = [
    "Office Supplies",
    "Software as a Service (SaaS)",
    "Professional Services",
    "Marketing",
    "Travel & Entertainment",
    "Hardware & Equipment",
    "Utilities",
    "Rent & Facilities",
    "Insurance",
    "Financial Services"
]

# Configure Gemini API (to be set with environment variable)
def configure_gemini():
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if api_key:
        logger.info("Configuring Gemini API with provided API key")
        genai.configure(api_key=api_key)
        try:
            # Test if we can access the models
            models = genai.list_models()
            available_models = [model.name for model in models]
            logger.info(f"Available models: {available_models}")
            
            gemini_models = [model for model in available_models if 'gemini' in model.lower()]
            if gemini_models:
                logger.info(f"Found {len(gemini_models)} Gemini models: {gemini_models[:3]}...")
            else:
                logger.warning("Warning: No Gemini models found in available models")
            return True
        except Exception as e:
            logger.error(f"Error configuring Gemini API: {e}")
            return False
    logger.warning("No Gemini API key found in environment variables")
    return False

# Configure Groq API (to be set with environment variable)
def configure_groq():
    api_key = os.environ.get('GROQ_API_KEY', '')
    if api_key:
        logger.info("Configuring Groq API with provided API key")
        try:
            # Test the connection using direct HTTP request
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers=headers
            )
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            # Parse the response
            models_data = response.json()
            available_models = [model['id'] for model in models_data.get('data', [])]
            logger.info(f"Available Groq models: {available_models}")
            return True
        except Exception as e:
            logger.error(f"Error configuring Groq API: {e}")
            return False
    logger.warning("No Groq API key found in environment variables")
    return False

# Function to check if vendor is in cache
def check_vendor_in_cache(vendor_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Return results as dictionaries
        
        cursor.execute("SELECT category FROM vendor_categories_cache WHERE vendor_name = %s", (vendor_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logger.info(f"CACHE HIT: Found vendor '{vendor_name}' in cache with category '{result['category']}'")
            return result['category']
        
        logger.info(f"CACHE MISS: Vendor '{vendor_name}' not found in cache")
        return None
    except Exception as e:
        logger.error(f"CACHE ERROR: Error checking cache for '{vendor_name}': {e}")
        return None

# Function to add vendor to cache with retry logic for database locks
def add_vendor_to_cache(vendor_name, category, description=""):
    max_retries = 10
    retry_delay = 1.0  # seconds
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Add to cache with timestamp
            # For MySQL, use REPLACE INTO instead of INSERT OR REPLACE
            cursor.execute(
                "REPLACE INTO vendor_categories_cache (vendor_name, category, description, last_updated) VALUES (%s, %s, %s, %s)",
                (vendor_name, category, description, datetime.now().isoformat())
            )
            
            conn.commit()
            conn.close()
            logger.info(f"CACHE SUCCESS: Successfully added vendor '{vendor_name}' to cache")
            return True
        except MySQLError as e:
            if ("Lock wait timeout exceeded" in str(e) or "Deadlock found" in str(e)) and attempt < max_retries - 1:
                logger.warning(f"CACHE WARNING: Database lock issue, retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"CACHE ERROR: Error adding vendor '{vendor_name}' to cache after {attempt+1} attempts: {e}")
                if conn:
                    conn.close()
                return False
        except Exception as e:
            logger.error(f"CACHE ERROR: Error adding vendor '{vendor_name}' to cache: {e}")
            if conn:
                conn.close()
            return False
    
    # If we've exhausted all retries
    logger.error(f"CACHE ERROR: Failed to add vendor '{vendor_name}' to cache after {max_retries} attempts")
    return False

# Rule-based categorization as fallback when API is unavailable
def rule_based_categorization(vendor_name, vendor_description=""):
    """Categorize vendor using simple keyword matching rules"""
    logger.info(f"RULE-BASED CATEGORIZATION: Starting for vendor '{vendor_name}'")
    
    vendor_name = vendor_name.lower()
    vendor_description = vendor_description.lower() if vendor_description else ""
    combined_text = f"{vendor_name} {vendor_description}"
    
    # Define keyword mappings to categories
    category_keywords = {
        "Office Supplies": ["office", "supplies", "paper", "staples", "pens", "stationary"],
        "Software as a Service (SaaS)": ["software", "saas", "cloud", "subscription", "license", "microsoft", "adobe", "salesforce"],
        "Professional Services": ["consulting", "advisor", "service", "professional", "legal", "accounting", "deloitte", "pwc", "kpmg", "ey"],
        "Marketing": ["marketing", "advertising", "media", "facebook", "google ads", "promotion", "campaign"],
        "Travel & Entertainment": ["travel", "airline", "hotel", "flight", "booking", "transportation", "delta", "airbnb"],
        "Hardware & Equipment": ["hardware", "computer", "laptop", "server", "equipment", "device", "dell", "hp", "apple"],
        "Utilities": ["utility", "electric", "water", "gas", "power", "telecom", "internet", "phone", "at&t", "verizon"],
        "Rent & Facilities": ["rent", "lease", "facility", "office space", "building", "property", "wework", "regus"],
        "Insurance": ["insurance", "policy", "coverage", "risk", "allstate", "geico", "prudential"],
        "Financial Services": ["financial", "banking", "investment", "loan", "credit", "chase", "bank", "capital"]
    }
    
    # Check for keyword matches
    best_match = None
    max_matches = 0
    match_details = []
    
    for category, keywords in category_keywords.items():
        category_matches = [keyword for keyword in keywords if keyword in combined_text]
        matches = len(category_matches)
        
        if matches > 0:
            match_details.append(f"Category '{category}': {matches} matches {category_matches}")
            
        if matches > max_matches:
            max_matches = matches
            best_match = category
    
    # Log match details
    if match_details:
        logger.info(f"KEYWORD MATCHES for '{vendor_name}':\n" + "\n".join(match_details))
    
    # If no matches found, use a default category
    if not best_match or max_matches == 0:
        best_match = ALLOWED_CATEGORIES[0]
        logger.warning(f"No keyword matches found for '{vendor_name}', using default category: {best_match}")
    else:
        logger.info(f"RULE-BASED RESULT: Categorized '{vendor_name}' as '{best_match}' with {max_matches} keyword matches")
    
    # Add to cache
    add_vendor_to_cache(vendor_name, best_match, vendor_description)
    
    return best_match

# Function to get vendor category from cache
def get_vendor_from_cache(vendor_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Case-insensitive search for vendor name
        cursor.execute(
            "SELECT category FROM vendor_categories_cache WHERE LOWER(vendor_name) = LOWER(%s) LIMIT 1",
            (vendor_name,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logger.info(f"CACHE: Found category '{result['category']}' for vendor '{vendor_name}'")
            return result['category']
        else:
            logger.info(f"CACHE: No category found for vendor '{vendor_name}'")
            return None
    except Exception as e:
        logger.error(f"CACHE ERROR: Error looking up vendor in cache: {str(e)}")
        return None

# Function to categorize vendor using cache or API (Gemini or Groq)
def categorize_vendor(vendor_name, vendor_description=""):
    # First check if vendor exists in cache
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category:
        logger.info(f"CACHE HIT: Using cached category for '{vendor_name}': {cached_category}")
        return cached_category
    
    logger.info(f"CACHE MISS: No cached category found for '{vendor_name}'")
    
    # Create the prompt (same for both APIs)
    prompt = f"""You are a professional business analyst specializing in vendor and spend categorization. 
    Your task is to analyze a vendor and assign a single category from the provided list.

    Vendor Name: {vendor_name}
    Vendor Description: {vendor_description}

    Allowed Categories:
    {', '.join(ALLOWED_CATEGORIES)}

    Output only the single, best-fit category name. Do not include any other text, explanations, or formatting."""
    
    logger.info(f"API REQUEST for '{vendor_name}':\n{prompt}")
    
    # Try Gemini API first
    gemini_configured = configure_gemini()
    if gemini_configured:
        try:
            logger.info(f"Attempting to categorize '{vendor_name}' using Gemini API")
            # Try to get available models and use an appropriate one
            models = genai.list_models()
            gemini_models = [model.name for model in models if 'gemini' in model.name.lower()]
            
            if gemini_models:
                model_name = gemini_models[0]  # Use the first available Gemini model
                logger.info(f"Using Gemini model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                # Call Gemini API
                response = model.generate_content(prompt)
                
                # Process and validate response
                category = response.text.strip()
                logger.info(f"GEMINI API RESPONSE for '{vendor_name}':\n{category}")
                
                if category in ALLOWED_CATEGORIES:
                    logger.info(f"VALID CATEGORY: '{category}' for vendor '{vendor_name}' from Gemini API")
                    # Add to cache for future use
                    add_vendor_to_cache(vendor_name, category, vendor_description)
                    return category
                else:
                    logger.warning(f"INVALID CATEGORY: Gemini API returned invalid category: '{category}' for vendor '{vendor_name}'")
            else:
                logger.warning("No Gemini models available")
        except Exception as e:
            logger.error(f"GEMINI API ERROR: Error calling Gemini API for '{vendor_name}': {e}")
    else:
        logger.warning("Gemini API not configured or unavailable")
    
    # If Gemini API failed or returned invalid category, try Groq API
    groq_configured = configure_groq()
    if groq_configured:
        try:
            logger.info(f"Attempting to categorize '{vendor_name}' using Groq API")
            # Prepare the request for Groq API
            api_key = os.environ.get('GROQ_API_KEY')
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare the request body
            data = {
                "model": "llama3-70b-8192",
                "messages": [
                    {"role": "system", "content": "You are a professional business analyst specializing in vendor categorization."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 100
            }
            
            # Call Groq API with LLama 3 model
            logger.info(f"Using Groq model: llama3-70b-8192")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            response_data = response.json()
            
            # Process and validate response
            category = response_data['choices'][0]['message']['content'].strip()
            logger.info(f"GROQ API RESPONSE for '{vendor_name}':\n{category}")
            
            if category in ALLOWED_CATEGORIES:
                logger.info(f"VALID CATEGORY: '{category}' for vendor '{vendor_name}' from Groq API")
                # Add to cache for future use
                add_vendor_to_cache(vendor_name, category, vendor_description)
                return category
            else:
                logger.warning(f"INVALID CATEGORY: Groq API returned invalid category: '{category}' for vendor '{vendor_name}', using rule-based categorization")
                return rule_based_categorization(vendor_name, vendor_description)
                
        except Exception as e:
            logger.error(f"GROQ API ERROR: Error calling Groq API for '{vendor_name}': {e}")
    else:
        logger.warning("Groq API not configured or unavailable")
    
    # If both APIs failed or returned invalid categories, use rule-based categorization
    logger.warning(f"All APIs failed or unavailable, using rule-based categorization for '{vendor_name}'")
    return rule_based_categorization(vendor_name, vendor_description)

# Routes
@app.route('/')
def index():
    # Check if there are any records in the vendor_categories_cache table
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT COUNT(*) as count FROM vendor_categories_cache')
        result = cursor.fetchone()
        count = result['count'] if result else 0
        
        logger.info(f"INDEX: Found {count} records in vendor_categories_cache table")
        
        # If no records, add a sample record
        if count == 0:
            logger.info("INDEX: Adding sample record to vendor_categories_cache table")
            add_vendor_to_cache("Sample Vendor", "Food", "This is a sample vendor added automatically")
            logger.info("INDEX: Sample record added to vendor_categories_cache table")
        
        conn.close()
    except Exception as e:
        logger.error(f"INDEX ERROR: Failed to check/add sample cache record - {str(e)}")
    
    return render_template('index.html', categories=ALLOWED_CATEGORIES)

@app.route('/upload', methods=['POST'])
def upload_file():
    logger.info("UPLOAD: Processing file upload request")
    if 'file' not in request.files:
        logger.warning("UPLOAD ERROR: No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("UPLOAD ERROR: Empty filename")
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.csv'):
        logger.warning(f"UPLOAD ERROR: Invalid file format - {file.filename}")
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        logger.info(f"UPLOAD: Processing file {file.filename}")
        # Save the file temporarily
        filename = file.filename
        file_path = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(file_path)
        
        # Process the file
        df = pd.read_csv(file_path)
        
        # Store upload info in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add upload record
        cursor.execute(
            "INSERT INTO uploads (filename, upload_date) VALUES (%s, %s)",
            (filename, datetime.now().isoformat())
        )
        conn.commit()  # Commit to get the last insert ID
        upload_id = cursor.lastrowid
        
        # Process each vendor
        vendor_column = df.columns[0]  # First column is vendor name
        description_column = df.columns[1] if len(df.columns) > 1 else None  # Second column is description if it exists
        
        vendors_to_process = []
        
        for _, row in df.iterrows():
            vendor_name = row[vendor_column]
            vendor_description = row[description_column] if description_column and not pd.isna(row[description_column]) else ""
            
            logger.info(f"Processing vendor: {vendor_name}, Description: {vendor_description}")
            
            # Check if vendor exists in cache
            ai_category = get_vendor_from_cache(vendor_name)
            cache_hit = True if ai_category else False
            
            if not ai_category:
                # If not in cache, use AI to categorize
                logger.info(f"Vendor '{vendor_name}' not found in cache, using AI categorization")
                ai_category = categorize_vendor(vendor_name, vendor_description)
                cache_hit = False
            
            # Add to database
            cursor.execute(
                "INSERT INTO categorized_vendors (upload_id, vendor_name, original_category, ai_category) VALUES (%s, %s, %s, %s)",
                (upload_id, vendor_name, "", ai_category)
            )
            vendor_id = cursor.lastrowid
            
            vendors_to_process.append({
                'id': vendor_id,
                'vendor_name': vendor_name,
                'original_category': "",
                'ai_category': ai_category,
                'description': vendor_description,
                'cache_hit': cache_hit
            })
        
        conn.commit()
        conn.close()
        
        # Clean up
        os.remove(file_path)
        
        logger.info(f"Successfully processed upload: {filename} with {len(vendors_to_process)} vendors")
        return jsonify({
            'success': True,
            'upload_id': upload_id,
            'vendors': vendors_to_process
        })
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    logger.info("HISTORY: Retrieving upload history")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Return results as dictionaries
        
        cursor.execute('''
            SELECT u.id, u.filename, u.upload_date as upload_timestamp, COUNT(v.id) as vendor_count
            FROM uploads u
            LEFT JOIN categorized_vendors v ON u.id = v.upload_id
            GROUP BY u.id
            ORDER BY u.upload_date DESC
        ''')
        
        history = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts for JSON serialization
        history_list = list(history)  # MySQL connector already returns dictionaries
        
        logger.info(f"HISTORY: Retrieved {len(history_list)} upload records")
        return jsonify(history_list)
    except Exception as e:
        logger.error(f"HISTORY ERROR: Failed to retrieve history - {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/history/<int:upload_id>')
def get_upload_details(upload_id):
    logger.info(f"HISTORY DETAIL: Retrieving details for upload ID {upload_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Return results as dictionaries
        
        # Get upload details
        cursor.execute("SELECT * FROM uploads WHERE id = %s", (upload_id,))
        upload = cursor.fetchone()
        
        if not upload:
            logger.warning(f"HISTORY DETAIL ERROR: Upload ID {upload_id} not found")
            return jsonify({'error': 'Upload not found'}), 404
        
        logger.info(f"HISTORY DETAIL: Found upload record: {upload}")
        
        # Get vendors for this upload
        cursor.execute("SELECT * FROM categorized_vendors WHERE upload_id = %s", (upload_id,))
        vendors = cursor.fetchall()
        
        # MySQL connector already returns dictionaries
        upload_dict = dict(upload)
        vendors_list = list(vendors)
        
        logger.info(f"HISTORY DETAIL: Found {len(vendors_list)} vendor records")
        if len(vendors_list) > 0:
            logger.info(f"HISTORY DETAIL: Sample vendor record: {vendors_list[0]}")
        
        conn.close()
        
        response_data = {
            'upload': upload_dict,
            'vendors': vendors_list
        }
        
        logger.info(f"HISTORY DETAIL: Sending response with {len(vendors_list)} vendors and upload ID {upload_id}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"HISTORY DETAIL ERROR: Failed to retrieve details for upload ID {upload_id} - {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to get allowed categories
@app.route('/categories')
def get_categories():
    logger.info("CATEGORIES API: Retrieving allowed categories list")
    return jsonify(ALLOWED_CATEGORIES)

# Route to get all cached vendors
@app.route('/cache', methods=['GET'])
def get_cache():
    logger.info("CACHE API: Retrieving all cached vendors")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # Return results as dictionaries
        
        # Log database connection status
        logger.info(f"CACHE API: Database connection established: {conn is not None}")
        
        cursor.execute('SELECT * FROM vendor_categories_cache ORDER BY vendor_name')
        cache_rows = cursor.fetchall()
        
        # Log raw results
        logger.info(f"CACHE API: Raw fetch result type: {type(cache_rows)}, empty: {cache_rows is None or len(cache_rows) == 0}")
        
        conn.close()
        
        # MySQL connector already returns dictionaries
        cache_list = list(cache_rows) if cache_rows else []
        
        # Log the final result
        logger.info(f"CACHE API: Retrieved {len(cache_list)} cached vendor records")
        logger.info(f"CACHE API: First few records: {str(cache_list[:3]) if cache_list else '[]'}")
        
        return jsonify(cache_list)
    except Exception as e:
        logger.error(f"CACHE API ERROR: Failed to retrieve cache - {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to add a vendor to cache
@app.route('/cache', methods=['POST'])
def add_to_cache():
    logger.info("CACHE API: Adding vendor to cache")
    try:
        data = request.json
        
        if not data or 'vendor_name' not in data or 'category' not in data:
            logger.warning("CACHE API ERROR: Missing required fields in request")
            return jsonify({'error': 'Missing required fields'}), 400
        
        vendor_name = data['vendor_name']
        category = data['category']
        description = data.get('description', '')
        
        # Validate category
        if category not in ALLOWED_CATEGORIES:
            logger.warning(f"CACHE API ERROR: Invalid category '{category}'")
            return jsonify({'error': 'Invalid category'}), 400
        
        # Add to cache
        success = add_vendor_to_cache(vendor_name, category, description)
        
        if success:
            # Get the ID of the inserted/updated row
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM vendor_categories_cache WHERE vendor_name = %s", (vendor_name,))
            result = cursor.fetchone()
            cache_id = result['id'] if result else None
            conn.close()
            
            logger.info(f"CACHE API SUCCESS: Added/updated vendor '{vendor_name}' with ID {cache_id}")
            return jsonify({'success': True, 'cache_id': cache_id})
        else:
            logger.error(f"CACHE API ERROR: Failed to add vendor '{vendor_name}' to cache")
            return jsonify({'error': 'Failed to add vendor to cache'}), 500
    except Exception as e:
        logger.error(f"CACHE API ERROR: Failed to add vendor to cache - {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to delete a vendor from cache
@app.route('/cache/<int:cache_id>', methods=['DELETE'])
def delete_from_cache(cache_id):
    logger.info(f"CACHE API: Deleting vendor with ID {cache_id} from cache")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get vendor name for logging
        cursor.execute("SELECT vendor_name FROM vendor_categories_cache WHERE id = %s", (cache_id,))
        vendor = cursor.fetchone()
        
        if not vendor:
            logger.warning(f"CACHE API ERROR: Vendor with ID {cache_id} not found")
            return jsonify({'error': 'Vendor not found'}), 404
        
        vendor_name = vendor['vendor_name']
        
        # Delete from cache
        cursor.execute("DELETE FROM vendor_categories_cache WHERE id = %s", (cache_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"CACHE API SUCCESS: Deleted vendor '{vendor_name}' with ID {cache_id} from cache")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"CACHE API ERROR: Failed to delete vendor with ID {cache_id} - {str(e)}")
        return jsonify({'error': str(e)}), 500

# Test API connectivity when app starts
def test_api_connectivity():
    logger.info("\n===== Testing API Connectivity =====")
    
    # Test Gemini API
    gemini_configured = configure_gemini()
    if not gemini_configured:
        logger.warning("❌ Gemini API is not configured. Set GEMINI_API_KEY environment variable.")
    else:
        try:
            # Test categorization with a simple vendor
            logger.info("Testing Gemini API categorization with vendor: Test Vendor")
            prompt = "Categorize this vendor: Test Vendor, This is a test vendor for API connectivity check into one of these categories: Office Supplies, Software as a Service (SaaS), Professional Services"
            
            # Try to get available models and use an appropriate one
            models = genai.list_models()
            gemini_models = [model.name for model in models if 'gemini' in model.name.lower()]
            
            if gemini_models:
                model_name = gemini_models[0]  # Use the first available Gemini model
                logger.info(f"Using model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                # Log the API request
                logger.info(f"GEMINI API TEST REQUEST:\n{prompt}")
                
                # Call Gemini API
                response = model.generate_content(prompt)
                
                # Log the API response
                logger.info(f"GEMINI API TEST RESPONSE:\n{response.text}")
                
                logger.info("✅ Gemini API test successful!")
            else:
                logger.warning("❌ No Gemini models available for testing")
        except Exception as e:
            logger.error(f"❌ Gemini API test failed: {e}")
    
    # Test Groq API
    groq_configured = configure_groq()
    if not groq_configured:
        logger.warning("❌ Groq API is not configured. Set GROQ_API_KEY environment variable.")
    else:
        try:
            # Test categorization with a simple vendor
            logger.info("Testing Groq API categorization with vendor: Test Vendor")
            prompt = "Categorize this vendor: Test Vendor, This is a test vendor for API connectivity check into one of these categories: Office Supplies, Software as a Service (SaaS), Professional Services"
            
            # Prepare the request for Groq API
            api_key = os.environ.get('GROQ_API_KEY')
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare the request body
            data = {
                "model": "llama3-70b-8192",
                "messages": [
                    {"role": "system", "content": "You are a professional business analyst specializing in vendor categorization."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 100
            }
            
            # Log the API request
            logger.info(f"GROQ API TEST REQUEST:\n{prompt}")
            
            # Call Groq API with LLama 3 model
            logger.info(f"Using Groq model: llama3-70b-8192")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            response_data = response.json()
            
            # Log the API response
            logger.info(f"GROQ API TEST RESPONSE:\n{response_data['choices'][0]['message']['content']}")
            
            logger.info("✅ Groq API test successful!")
        except Exception as e:
            logger.error(f"❌ Groq API test failed: {e}")
            
    # Summary of API availability
    if gemini_configured or groq_configured:
        logger.info("✅ At least one API is available for use")
    else:
        logger.warning("❌ No APIs are available. Using rule-based categorization only.")

if __name__ == '__main__':
    # Run API test
    test_api_connectivity()
    app.run(host='0.0.0.0', port=5000, debug=True)
