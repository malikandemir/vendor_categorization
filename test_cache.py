#!/usr/bin/env python3
import os
import mysql.connector
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cache_test')

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', 'password'),
    'database': os.environ.get('MYSQL_DATABASE', 'vendor_categorization'),
    'port': int(os.environ.get('MYSQL_PORT', 3306))
}

def initialize_database():
    """Initialize database and create tables if they don't exist"""
    try:
        # First, create the database if it doesn't exist
        try:
            temp_conn = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
            temp_conn.close()
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            return False
        
        # Now connect to the database and create tables
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create vendor_cache table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendor_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            vendor_name VARCHAR(255) UNIQUE,
            category VARCHAR(255),
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create history table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(255),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            vendor_count INT,
            categorized_count INT
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def get_vendor_from_cache(vendor_name):
    """Check if vendor exists in cache"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT category, description FROM vendor_cache WHERE vendor_name = %s", (vendor_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            category = result['category']
            logger.info(f"CACHE HIT: Found '{vendor_name}' in cache with category '{category}'")
            return category
        else:
            logger.info(f"CACHE MISS: '{vendor_name}' not found in cache")
            return None
    except Exception as e:
        logger.error(f"Error checking cache: {e}")
        return None

def add_vendor_to_cache(vendor_name, category, description=""):
    """Add vendor to cache"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if vendor already exists in cache
        cursor.execute("SELECT COUNT(*) FROM vendor_cache WHERE vendor_name = %s", (vendor_name,))
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Update existing entry
            cursor.execute(
                "UPDATE vendor_cache SET category = %s, description = %s WHERE vendor_name = %s",
                (category, description, vendor_name)
            )
            logger.info(f"CACHE UPDATE: Updated '{vendor_name}' in cache with category '{category}'")
        else:
            # Insert new entry
            cursor.execute(
                "INSERT INTO vendor_cache (vendor_name, category, description) VALUES (%s, %s, %s)",
                (vendor_name, category, description)
            )
            logger.info(f"CACHE ADD: Added '{vendor_name}' to cache with category '{category}'")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error adding to cache: {e}")
        return False

def clear_cache_for_vendor(vendor_name):
    """Clear cache for a specific vendor"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendor_cache WHERE vendor_name = %s", (vendor_name,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"CACHE CLEAR: Removed '{vendor_name}' from cache")
        else:
            logger.info(f"CACHE CLEAR: '{vendor_name}' not found in cache")
        
        return deleted
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return False

def test_cache_functionality():
    """Test cache functionality"""
    logger.info("===== Testing Cache Functionality =====")
    
    # Test vendor
    vendor_name = "Test Cache Vendor"
    category = "Software as a Service (SaaS)"
    description = "This is a test vendor for cache functionality"
    
    # Clear cache for test vendor if it exists
    clear_cache_for_vendor(vendor_name)
    
    # Check if vendor exists in cache (should be a miss)
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category is None:
        logger.info("✅ Cache miss test passed")
    else:
        logger.error(f"❌ Cache miss test failed: Expected None, got '{cached_category}'")
    
    # Add vendor to cache
    add_vendor_to_cache(vendor_name, category, description)
    
    # Check if vendor exists in cache (should be a hit)
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category == category:
        logger.info("✅ Cache hit test passed")
    else:
        logger.error(f"❌ Cache hit test failed: Expected '{category}', got '{cached_category}'")
    
    # Update vendor in cache
    new_category = "Professional Services"
    add_vendor_to_cache(vendor_name, new_category, description)
    
    # Check if vendor was updated in cache
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category == new_category:
        logger.info("✅ Cache update test passed")
    else:
        logger.error(f"❌ Cache update test failed: Expected '{new_category}', got '{cached_category}'")
    
    # Clear cache for test vendor
    cleared = clear_cache_for_vendor(vendor_name)
    if cleared:
        logger.info("✅ Cache clear test passed")
    else:
        logger.error("❌ Cache clear test failed")
    
    # Check if vendor was removed from cache
    cached_category = get_vendor_from_cache(vendor_name)
    if cached_category is None:
        logger.info("✅ Cache clear verification test passed")
    else:
        logger.error(f"❌ Cache clear verification test failed: Expected None, got '{cached_category}'")

if __name__ == "__main__":
    # Initialize database first
    if initialize_database():
        # Test cache functionality
        test_cache_functionality()
    else:
        logger.error("Failed to initialize database, skipping cache tests")
