#!/usr/bin/env python3
import os
import sqlite3
import logging
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cache_ui_test')

# Database path
DB_PATH = 'data/vendor_cache.db'

def initialize_database():
    """Initialize database and create tables if they don't exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create vendor_cache table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendor_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT UNIQUE,
            category TEXT,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def add_vendor_to_cache(vendor_name, category, description=""):
    """Add vendor to cache"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if vendor already exists in cache
        cursor.execute("SELECT COUNT(*) FROM vendor_cache WHERE vendor_name = ?", (vendor_name,))
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Update existing entry
            cursor.execute(
                "UPDATE vendor_cache SET category = ?, description = ? WHERE vendor_name = ?",
                (category, description, vendor_name)
            )
            logger.info(f"CACHE UPDATE: Updated '{vendor_name}' in cache with category '{category}'")
        else:
            # Insert new entry
            cursor.execute(
                "INSERT INTO vendor_cache (vendor_name, category, description) VALUES (?, ?, ?)",
                (vendor_name, category, description)
            )
            logger.info(f"CACHE ADD: Added '{vendor_name}' to cache with category '{category}'")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding to cache: {e}")
        return False

def populate_test_cache():
    """Populate cache with test data"""
    test_vendors = [
        ("Microsoft", "Software as a Service (SaaS)", "Cloud computing and software provider"),
        ("Deloitte", "Professional Services", "Global consulting and advisory firm"),
        ("Amazon Web Services", "Software as a Service (SaaS)", "Cloud infrastructure and services provider"),
        ("Office Depot", "Office Supplies", "Office supplies and furniture retailer"),
        ("Accenture", "Professional Services", "Global professional services company"),
        ("Slack", "Software as a Service (SaaS)", "Business communication platform"),
        ("UPS", "Shipping and Logistics", "Package delivery and supply chain management"),
        ("Wework", "Real Estate", "Shared workspace provider"),
        ("Adobe", "Software as a Service (SaaS)", "Creative and marketing software provider"),
        ("Staples", "Office Supplies", "Office supplies and equipment retailer")
    ]
    
    for vendor_name, category, description in test_vendors:
        add_vendor_to_cache(vendor_name, category, description)
    
    logger.info(f"Added {len(test_vendors)} vendors to cache")

def test_cache_ui(base_url="http://127.0.0.1:5000"):
    """Test cache management UI"""
    logger.info("===== Testing Cache Management UI =====")
    
    # Test accessing cache management page
    try:
        response = requests.get(f"{base_url}/cache")
        if response.status_code == 200:
            logger.info("✅ Cache management page accessible")
            return True
        else:
            logger.error(f"❌ Failed to access cache management page: Status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error accessing cache management page: {e}")
        return False

if __name__ == "__main__":
    # Initialize database first
    if initialize_database():
        # Populate cache with test data
        populate_test_cache()
        
        # Test cache management UI
        test_cache_ui()
    else:
        logger.error("Failed to initialize database, skipping cache UI tests")
