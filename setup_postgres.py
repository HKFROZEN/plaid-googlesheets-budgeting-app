#!/usr/bin/env python3
"""
PostgreSQL Setup Script for Plaid Budgeting App

This script handles:
1. PostgreSQL database initialization
2. Schema creation
3. Data migration from SQLite to PostgreSQL
4. Environment configuration

Usage:
    python setup_postgres.py --init                    # Initialize new PostgreSQL database
    python setup_postgres.py --migrate                 # Migrate from SQLite to PostgreSQL
    python setup_postgres.py --init --migrate          # Initialize and migrate
    python setup_postgres.py --reset                   # Reset database (development only)
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
import sqlite3
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Optional, Dict, Any
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('postgres_setup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PostgreSQLSetup:
    def __init__(self):
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
            'database': os.getenv('POSTGRES_DB', 'plaid_budgeting_app')
        }
        
        self.sqlite_path = os.getenv('SQLITE_DB_PATH', 'plaid_app.db')
        self.sql_dir = Path('sql')
        
        # Ensure SQL directory exists
        self.sql_dir.mkdir(exist_ok=True)
        
        logger.info(f"PostgreSQL config: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
        logger.info(f"SQLite source: {self.sqlite_path}")
    
    def check_postgres_connection(self) -> bool:
        """Check if PostgreSQL server is running and accessible"""
        try:
            # Connect to PostgreSQL server (not specific database)
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database='postgres'  # Connect to default postgres database
            )
            conn.close()
            logger.info("PostgreSQL connection successful")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False
    
    def create_database(self) -> bool:
        """Create the PostgreSQL database if it doesn't exist"""
        try:
            # Connect to PostgreSQL server
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (self.db_config['database'],)
            )
            
            if cursor.fetchone():
                logger.info(f"Database '{self.db_config['database']}' already exists")
            else:
                # Create database
                cursor.execute(f"CREATE DATABASE {self.db_config['database']}")
                logger.info(f"Database '{self.db_config['database']}' created successfully")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False
    
    def run_sql_file(self, filename: str) -> bool:
        """Execute a SQL file against the PostgreSQL database"""
        try:
            sql_file = self.sql_dir / filename
            if not sql_file.exists():
                logger.error(f"SQL file not found: {sql_file}")
                return False
            
            # Connect to the application database
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Read and execute SQL file
            with open(sql_file, 'r') as f:
                sql_content = f.read()
            
            # Execute the SQL (handle multiple statements)
            cursor.execute(sql_content)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            logger.info(f"Successfully executed SQL file: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute SQL file {filename}: {e}")
            return False
    
    def init_database(self) -> bool:
        """Initialize the PostgreSQL database with schema"""
        logger.info("Initializing PostgreSQL database...")
        
        if not self.check_postgres_connection():
            return False
        
        if not self.create_database():
            return False
        
        if not self.run_sql_file('01_create_schema.sql'):
            return False
        
        logger.info("Database initialization completed successfully")
        return True
    
    def migrate_from_sqlite(self) -> bool:
        """Migrate data from SQLite to PostgreSQL"""
        logger.info("Starting migration from SQLite to PostgreSQL...")
        
        if not os.path.exists(self.sqlite_path):
            logger.warning(f"SQLite database not found at {self.sqlite_path}")
            return True  # Not an error if no existing data
        
        try:
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_path)
            sqlite_conn.row_factory = sqlite3.Row
            
            # Connect to PostgreSQL
            postgres_conn = psycopg2.connect(**self.db_config)
            postgres_cursor = postgres_conn.cursor()
            
            # Migrate tables in order (respecting foreign keys)
            self._migrate_users(sqlite_conn, postgres_cursor)
            self._migrate_user_tokens(sqlite_conn, postgres_cursor)
            self._migrate_accounts(sqlite_conn, postgres_cursor)
            self._migrate_transactions(sqlite_conn, postgres_cursor)
            
            # Update sequences to avoid conflicts
            self._update_sequences(postgres_cursor)
            
            postgres_conn.commit()
            postgres_cursor.close()
            postgres_conn.close()
            sqlite_conn.close()
            
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _migrate_users(self, sqlite_conn, postgres_cursor):
        """Migrate users table"""
        logger.info("Migrating users table...")
        
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("SELECT * FROM users")
        
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO users (id, username, password_hash, salt, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
            """, (row['id'], row['username'], row['password_hash'], row['salt'], row['created_at']))
        
        logger.info(f"Migrated {sqlite_cursor.rowcount} users")
    
    def _migrate_user_tokens(self, sqlite_conn, postgres_cursor):
        """Migrate user_tokens table"""
        logger.info("Migrating user_tokens table...")
        
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("SELECT * FROM user_tokens")
        
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO user_tokens (id, user_id, access_token, item_id, public_token, 
                                       institution_id, institution_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (row['id'], row['user_id'], row['access_token'], row['item_id'], 
                  row['public_token'], row['institution_id'], row['institution_name'],
                  row['created_at'], row['updated_at']))
        
        logger.info(f"Migrated {sqlite_cursor.rowcount} user tokens")
    
    def _migrate_accounts(self, sqlite_conn, postgres_cursor):
        """Migrate accounts table"""
        logger.info("Migrating accounts table...")
        
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("SELECT * FROM accounts")
        
        for row in sqlite_cursor.fetchall():
            # Convert SQLite integer boolean to PostgreSQL boolean
            is_active = bool(row['is_active']) if row['is_active'] is not None else True
            
            postgres_cursor.execute("""
                INSERT INTO accounts (id, user_id, token_id, account_id, name, type, subtype,
                                    institution_name, current_balance, available_balance,
                                    iso_currency_code, unofficial_currency_code, 
                                    account_classification, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, account_id) DO NOTHING
            """, (row['id'], row['user_id'], row['token_id'], row['account_id'], row['name'],
                  row['type'], row['subtype'], row['institution_name'], row['current_balance'],
                  row['available_balance'], row['iso_currency_code'], row['unofficial_currency_code'],
                  row['account_classification'], is_active, row['created_at'], row['updated_at']))
        
        logger.info(f"Migrated {sqlite_cursor.rowcount} accounts")
    
    def _migrate_transactions(self, sqlite_conn, postgres_cursor):
        """Migrate transactions table"""
        logger.info("Migrating transactions table...")
        
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("SELECT * FROM transactions")
        
        for row in sqlite_cursor.fetchall():
            # Convert SQLite integer boolean to PostgreSQL boolean
            pending = bool(row['pending']) if row['pending'] is not None else False
            
            postgres_cursor.execute("""
                INSERT INTO transactions (id, user_id, account_id, transaction_id, amount,
                                        iso_currency_code, unofficial_currency_code, date,
                                        datetime, authorized_date, authorized_datetime, name,
                                        merchant_name, account_owner, category, subcategory,
                                        transaction_type, pending, institution_name, 
                                        created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, transaction_id) DO NOTHING
            """, (row['id'], row['user_id'], row['account_id'], row['transaction_id'], row['amount'],
                  row['iso_currency_code'], row['unofficial_currency_code'], row['date'],
                  row['datetime'], row['authorized_date'], row['authorized_datetime'], row['name'],
                  row['merchant_name'], row['account_owner'], row['category'], row['subcategory'],
                  row['transaction_type'], pending, row['institution_name'],
                  row['created_at'], row['updated_at']))
        
        logger.info(f"Migrated {sqlite_cursor.rowcount} transactions")
    
    def _update_sequences(self, postgres_cursor):
        """Update PostgreSQL sequences after data migration"""
        logger.info("Updating PostgreSQL sequences...")
        
        sequences = [
            ('users_id_seq', 'users'),
            ('user_tokens_id_seq', 'user_tokens'),
            ('accounts_id_seq', 'accounts'),
            ('transactions_id_seq', 'transactions')
        ]
        
        for seq_name, table_name in sequences:
            postgres_cursor.execute(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {table_name}), 1))")
    
    def reset_database(self) -> bool:
        """Reset the database (development only)"""
        logger.warning("Resetting database - ALL DATA WILL BE LOST!")
        
        if not self.run_sql_file('03_cleanup.sql'):
            return False
        
        if not self.run_sql_file('01_create_schema.sql'):
            return False
        
        logger.info("Database reset completed")
        return True
    
    def create_env_example(self):
        """Create a .env.example file with PostgreSQL configuration"""
        env_example = """# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=plaid_budgeting_app

# SQLite Configuration (for migration)
SQLITE_DB_PATH=plaid_app.db

# Plaid Configuration
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox

# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
"""
        
        with open('.env.example', 'w') as f:
            f.write(env_example)
        
        logger.info("Created .env.example file")

def main():
    parser = argparse.ArgumentParser(description='PostgreSQL Setup for Plaid Budgeting App')
    parser.add_argument('--init', action='store_true', help='Initialize PostgreSQL database')
    parser.add_argument('--migrate', action='store_true', help='Migrate from SQLite to PostgreSQL')
    parser.add_argument('--reset', action='store_true', help='Reset database (development only)')
    parser.add_argument('--create-env', action='store_true', help='Create .env.example file')
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    setup = PostgreSQLSetup()
    success = True
    
    if args.create_env:
        setup.create_env_example()
    
    if args.reset:
        if not setup.reset_database():
            success = False
    
    if args.init:
        if not setup.init_database():
            success = False
    
    if args.migrate:
        if not setup.migrate_from_sqlite():
            success = False
    
    if success:
        logger.info("Setup completed successfully!")
    else:
        logger.error("Setup failed. Check logs for details.")
        sys.exit(1)

if __name__ == '__main__':
    main() 