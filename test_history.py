#!/usr/bin/env python3
import os
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('history_test')

# Database path
DB_PATH = 'data/vendor_cache.db'

def initialize_database():
    """Initialize database and create tables if they don't exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create history table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            vendor_count INTEGER,
            categorized_count INTEGER
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def add_to_history(filename, vendor_count, categorized_count):
    """Add an entry to the history table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert new history entry
        cursor.execute(
            "INSERT INTO history (filename, timestamp, vendor_count, categorized_count) VALUES (?, ?, ?, ?)",
            (filename, datetime.now(), vendor_count, categorized_count)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"HISTORY ADD: Added '{filename}' to history with {vendor_count} vendors, {categorized_count} categorized")
        return True
    except Exception as e:
        logger.error(f"Error adding to history: {e}")
        return False

def get_history():
    """Get all entries from the history table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, timestamp, vendor_count, categorized_count FROM history ORDER BY timestamp DESC")
        results = cursor.fetchall()
        conn.close()
        
        if results:
            logger.info(f"HISTORY: Found {len(results)} entries in history")
            for result in results:
                id, filename, timestamp, vendor_count, categorized_count = result
                logger.info(f"HISTORY ENTRY: ID={id}, File={filename}, Time={timestamp}, Vendors={vendor_count}, Categorized={categorized_count}")
            return results
        else:
            logger.info("HISTORY: No entries found in history")
            return []
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return []

def clear_history():
    """Clear all entries from the history table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history")
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"HISTORY CLEAR: Removed all entries from history")
        else:
            logger.info(f"HISTORY CLEAR: No entries found in history")
        
        return deleted
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return False

def test_history_functionality():
    """Test history functionality"""
    logger.info("===== Testing History Functionality =====")
    
    # Clear history to start fresh
    clear_history()
    
    # Check if history is empty
    history_entries = get_history()
    if len(history_entries) == 0:
        logger.info("✅ History empty test passed")
    else:
        logger.error(f"❌ History empty test failed: Expected 0 entries, got {len(history_entries)}")
    
    # Add test entries to history
    add_to_history("test_file1.csv", 10, 8)
    add_to_history("test_file2.csv", 15, 12)
    add_to_history("test_file3.csv", 5, 5)
    
    # Check if history has the correct number of entries
    history_entries = get_history()
    if len(history_entries) == 3:
        logger.info("✅ History add test passed")
    else:
        logger.error(f"❌ History add test failed: Expected 3 entries, got {len(history_entries)}")
    
    # Clear history
    cleared = clear_history()
    if cleared:
        logger.info("✅ History clear test passed")
    else:
        logger.error("❌ History clear test failed")
    
    # Check if history is empty again
    history_entries = get_history()
    if len(history_entries) == 0:
        logger.info("✅ History clear verification test passed")
    else:
        logger.error(f"❌ History clear verification test failed: Expected 0 entries, got {len(history_entries)}")

if __name__ == "__main__":
    # Initialize database first
    if initialize_database():
        # Test history functionality
        test_history_functionality()
    else:
        logger.error("Failed to initialize database, skipping history tests")
