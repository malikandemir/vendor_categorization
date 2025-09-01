import mysql.connector
import os
from datetime import datetime

# Get database connection parameters from environment variables or use defaults
db_host = os.environ.get('MYSQL_HOST', 'localhost')
db_user = os.environ.get('MYSQL_USER', 'root')
db_password = os.environ.get('MYSQL_PASSWORD', 'password')
db_name = os.environ.get('MYSQL_DATABASE', 'vendor_categorization')

def get_db_connection():
    """Create a database connection"""
    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name
    )

def add_test_vendor():
    """Add a test vendor to the cache"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add test vendor
        vendor_name = f"Test Vendor {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        category = "Food"
        description = "This is a test vendor added via script"
        
        # Insert the vendor
        cursor.execute(
            "REPLACE INTO vendor_categories_cache (vendor_name, category, description, last_updated) VALUES (%s, %s, %s, %s)",
            (vendor_name, category, description, datetime.now().isoformat())
        )
        
        conn.commit()
        vendor_id = cursor.lastrowid
        
        print(f"Added test vendor with ID {vendor_id}")
        
        # Verify it was added
        cursor.execute("SELECT COUNT(*) FROM vendor_categories_cache")
        count = cursor.fetchone()[0]
        print(f"Total vendors in cache: {count}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding test vendor: {str(e)}")
        return False

if __name__ == "__main__":
    add_test_vendor()
