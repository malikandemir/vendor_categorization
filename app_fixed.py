import os
import sqlite3
import pandas as pd
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for
import google.generativeai as genai

app = Flask(__name__)

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect('vendor_categories.db', timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=60000')
    conn.row_factory = sqlite3.Row
    return conn

# Database initialization
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        upload_date TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categorized_vendors (
        id INTEGER PRIMARY KEY,
        upload_id INTEGER,
        vendor_name TEXT,
        category TEXT,
        description TEXT,
        FOREIGN KEY (upload_id) REFERENCES uploads (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendor_categories_cache (
        id INTEGER PRIMARY KEY,
        vendor_name TEXT UNIQUE,
        category TEXT,
        description TEXT,
        last_updated TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database at startup
init_db()

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
        genai.configure(api_key=api_key)
        try:
            # Test if we can access the models
            models = genai.list_models()
            available_models = [model.name for model in models]
            print(f"Available models: {available_models}")
            if not any('gemini' in model.lower() for model in available_models):
                print("Warning: No Gemini models found in available models")
            return True
        except Exception as e:
            print(f"Error configuring Gemini API: {e}")
            return False
    return False

# Function to check if vendor exists in cache
def get_vendor_from_cache(vendor_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Look for the vendor in the cache
        cursor.execute("SELECT category FROM vendor_categories_cache WHERE vendor_name = ? COLLATE NOCASE", (vendor_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result['category']
        return None
    except Exception as e:
        print(f"Error checking cache: {e}")
        return None

# Function to add vendor to cache
def add_vendor_to_cache(vendor_name, category, description=""):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add to cache with timestamp
        cursor.execute(
            "INSERT OR REPLACE INTO vendor_categories_cache (vendor_name, category, description, last_updated) VALUES (?, ?, ?, ?)",
            (vendor_name, category, description, datetime.now().isoformat())
        )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to cache: {e}")
        return False

# Rule-based categorization as fallback when API is unavailable
def rule_based_categorization(vendor_name, vendor_description=""):
    """Categorize vendor using simple keyword matching rules"""
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
    
    for category, keywords in category_keywords.items():
        matches = sum(1 for keyword in keywords if keyword in combined_text)
        if matches > max_matches:
            max_matches = matches
            best_match = category
    
    # If no matches found, use a default category
    if not best_match or max_matches == 0:
        best_match = ALLOWED_CATEGORIES[0]
        print(f"No keyword matches found for '{vendor_name}', using default category: {best_match}")
    else:
        print(f"Categorized '{vendor_name}' as '{best_match}' using rule-based matching")
    
    # Add to cache
    add_vendor_to_cache(vendor_name, best_match, vendor_description)
    
    return best_match

# Function to categorize vendor using cache or Gemini API
def categorize_vendor(vendor_name, vendor_description=""):
    # First check if vendor exists in cache
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category:
        print(f"Using cached category for {vendor_name}: {cached_category}")
        return cached_category
    
    # If not in cache, try to use Gemini API or fallback to rule-based categorization
    api_configured = configure_gemini()
    if not api_configured:
        print(f"API not configured, using rule-based categorization for {vendor_name}")
        return rule_based_categorization(vendor_name, vendor_description)
    
    try:
        # Create the prompt
        prompt = f"""You are a professional business analyst specializing in vendor and spend categorization. 
        Your task is to analyze a vendor and assign a single category from the provided list.

        Vendor Name: {vendor_name}
        Vendor Description: {vendor_description}

        Allowed Categories:
        {', '.join(ALLOWED_CATEGORIES)}

        Output only the single, best-fit category name. Do not include any other text, explanations, or formatting."""
        
        # Try to get available models and use an appropriate one
        try:
            models = genai.list_models()
            gemini_models = [model.name for model in models if 'gemini' in model.name.lower()]
            
            if gemini_models:
                model_name = gemini_models[0]  # Use the first available Gemini model
                print(f"Using model: {model_name}")
                model = genai.GenerativeModel(model_name)
            else:
                print("No Gemini models available, falling back to rule-based categorization")
                return rule_based_categorization(vendor_name, vendor_description)
                
            # Call Gemini API
            response = model.generate_content(prompt)
            
            # Process and validate response
            category = response.text.strip()
            if category in ALLOWED_CATEGORIES:
                # Add to cache for future use
                add_vendor_to_cache(vendor_name, category, vendor_description)
                return category
            else:
                print(f"API returned invalid category: {category}, using rule-based categorization")
                return rule_based_categorization(vendor_name, vendor_description)
                
        except Exception as inner_e:
            print(f"Error with model selection: {inner_e}")
            return rule_based_categorization(vendor_name, vendor_description)
    
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return rule_based_categorization(vendor_name, vendor_description)

# Routes
@app.route('/')
def index():
    return render_template('index.html', categories=ALLOWED_CATEGORIES)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Read CSV file
        df = pd.read_csv(file)
        
        # Ensure required columns exist
        if 'vendor_name' not in df.columns:
            return jsonify({'error': 'CSV must contain a vendor_name column'}), 400
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert upload record
        cursor.execute(
            "INSERT INTO uploads (filename, upload_date) VALUES (?, ?)",
            (file.filename, datetime.now().isoformat())
        )
        upload_id = cursor.lastrowid
        
        # Process each vendor
        results = []
        for _, row in df.iterrows():
            vendor_name = row['vendor_name']
            original_category = row.get('category', '')
            
            # Get vendor description if available
            vendor_description = row.get('description', '')
            
            # Categorize vendor
            ai_category = categorize_vendor(vendor_name, vendor_description)
            
            # Store result
            cursor.execute(
                "INSERT INTO categorized_vendors (upload_id, vendor_name, category, description) VALUES (?, ?, ?, ?)",
                (upload_id, vendor_name, ai_category, vendor_description)
            )
            
            results.append({
                'vendor_name': vendor_name,
                'original_category': original_category,
                'ai_category': ai_category
            })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'upload_id': upload_id,
            'results': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def get_history():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.filename, u.upload_date as upload_timestamp, COUNT(v.id) as vendor_count
            FROM uploads u
            LEFT JOIN categorized_vendors v ON u.id = v.upload_id
            GROUP BY u.id
            ORDER BY u.upload_date DESC
        ''')
        
        uploads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(uploads)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/<int:upload_id>')
def history_detail(upload_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get upload details
        cursor.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,))
        upload = dict(cursor.fetchone())
        
        # Get categorizations for this upload
        cursor.execute('''
            SELECT * FROM categorized_vendors 
            WHERE upload_id = ?
            ORDER BY vendor_name
        ''', (upload_id,))
        
        vendors = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'upload': upload,
            'vendors': vendors
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to get allowed categories
@app.route('/categories')
def get_categories():
    return jsonify(ALLOWED_CATEGORIES)

# Route to get all cached vendors
@app.route('/cache', methods=['GET'])
def get_cache():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM vendor_categories_cache ORDER BY vendor_name")
        cache_entries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(cache_entries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to add a vendor to cache
@app.route('/cache', methods=['POST'])
def add_to_cache():
    try:
        data = request.json
        vendor_name = data.get('vendor_name')
        category = data.get('category')
        description = data.get('description', '')
        
        if not vendor_name or not category or category not in ALLOWED_CATEGORIES:
            return jsonify({'error': 'Invalid data provided'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO vendor_categories_cache (vendor_name, category, description, last_updated) 
               VALUES (?, ?, ?, ?) 
               ON CONFLICT(vendor_name) 
               DO UPDATE SET category = ?, description = ?, last_updated = ?""",
            (vendor_name, category, description, datetime.now().isoformat(),
             category, description, datetime.now().isoformat())
        )
        conn.commit()
        
        # Get the ID of the inserted/updated row
        cursor.execute("SELECT id FROM vendor_categories_cache WHERE vendor_name = ?", (vendor_name,))
        cache_id = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({'success': True, 'id': cache_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Route to delete a vendor from cache
@app.route('/cache/<int:cache_id>', methods=['DELETE'])
def delete_from_cache(cache_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM vendor_categories_cache WHERE id = ?", (cache_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Test API connectivity at startup
def test_api_connectivity():
    print("\n===== Testing API Connectivity =====")
    api_configured = configure_gemini()
    if api_configured:
        print("✅ Gemini API is configured and accessible")
        try:
            # Test a simple categorization
            test_vendor = "Test Vendor"
            test_description = "This is a test vendor for API connectivity check"
            print(f"Testing categorization with vendor: {test_vendor}")
            
            # Try to get available models and use an appropriate one
            models = genai.list_models()
            gemini_models = [model.name for model in models if 'gemini' in model.name.lower()]
            
            if gemini_models:
                model_name = gemini_models[0]  # Use the first available Gemini model
                print(f"Using model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                # Create a simple prompt
                prompt = f"Categorize this vendor: {test_vendor}, {test_description} into one of these categories: {', '.join(ALLOWED_CATEGORIES[:3])}"
                
                # Call Gemini API
                response = model.generate_content(prompt)
                print(f"API Response: {response.text.strip()}")
                print("✅ API test successful")
            else:
                print("❌ No Gemini models available")
        except Exception as e:
            print(f"❌ API test failed: {e}")
    else:
        print("❌ Gemini API is not configured. Set GEMINI_API_KEY environment variable.")

if __name__ == '__main__':
    # Run API test
    test_api_connectivity()
    app.run(host='0.0.0.0', port=5000, debug=True)
