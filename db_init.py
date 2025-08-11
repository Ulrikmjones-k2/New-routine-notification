import sqlite3
import logging
import os

# Use persistent storage in Azure Functions, local storage otherwise
DATABASE_PATH = '/home/data/cache.db' if os.environ.get('WEBSITE_MOUNT_ENABLED') else 'cache.db'
DATA_DIRECTORY = '/home/data' if os.environ.get('WEBSITE_MOUNT_ENABLED') else '.'

def init_database():
    """
    Initialize the SQLite database and create the table if it doesn't exist
    """
    try:
        # Ensure the data directory exists (for Azure Functions)
        if os.environ.get('WEBSITE_MOUNT_ENABLED'):
            os.makedirs(DATA_DIRECTORY, exist_ok=True)
            
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routine_ids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info(f"📁 Database initialized: {DATABASE_PATH}")
        return True
    except Exception as e:
        logging.error(f"❌ Error initializing database: {str(e)}")
        return False