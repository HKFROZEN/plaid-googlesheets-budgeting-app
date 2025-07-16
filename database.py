import sqlite3
import hashlib
import secrets
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager

class DatabaseManager:
    """Manages SQLite database operations for user authentication and token storage"""
    
    def __init__(self, db_path: str = "plaid_app.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create user_tokens table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    access_token TEXT NOT NULL,
                    item_id TEXT,
                    public_token TEXT,
                    institution_id TEXT,
                    institution_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            # Create accounts table for caching account information
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_id INTEGER NOT NULL,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    subtype TEXT,
                    institution_name TEXT,
                    current_balance REAL,
                    available_balance REAL,
                    iso_currency_code TEXT DEFAULT 'USD',
                    unofficial_currency_code TEXT,
                    account_classification TEXT NOT NULL CHECK (account_classification IN ('asset', 'liability')),
                    custom_name TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (token_id) REFERENCES user_tokens (id) ON DELETE CASCADE,
                    UNIQUE(user_id, account_id)
                )
            ''')
            
            # Create transactions table for caching transaction data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    account_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    iso_currency_code TEXT DEFAULT 'USD',
                    unofficial_currency_code TEXT,
                    date DATE NOT NULL,
                    datetime TIMESTAMP,
                    authorized_date DATE,
                    authorized_datetime TIMESTAMP,
                    name TEXT NOT NULL,
                    merchant_name TEXT,
                    account_owner TEXT,
                    category TEXT,
                    subcategory TEXT,
                    transaction_type TEXT,
                    pending BOOLEAN DEFAULT FALSE,
                    institution_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, transaction_id)
                )
            ''')
            
            # Add institution columns to existing tables if they don't exist
            cursor.execute("PRAGMA table_info(user_tokens)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'institution_id' not in columns:
                cursor.execute('ALTER TABLE user_tokens ADD COLUMN institution_id TEXT')
            
            if 'institution_name' not in columns:
                cursor.execute('ALTER TABLE user_tokens ADD COLUMN institution_name TEXT')
            
            # Add category columns to transactions table if they don't exist
            cursor.execute("PRAGMA table_info(transactions)")
            transaction_columns = [column[1] for column in cursor.fetchall()]
            
            if 'category_primary' not in transaction_columns:
                cursor.execute('ALTER TABLE transactions ADD COLUMN category_primary TEXT')
            
            if 'category_detailed' not in transaction_columns:
                cursor.execute('ALTER TABLE transactions ADD COLUMN category_detailed TEXT')
            
            if 'category_confidence' not in transaction_columns:
                cursor.execute('ALTER TABLE transactions ADD COLUMN category_confidence TEXT')
            
            # Add custom_name column to accounts table if it doesn't exist
            cursor.execute("PRAGMA table_info(accounts)")
            account_columns = [column[1] for column in cursor.fetchall()]
            
            if 'custom_name' not in account_columns:
                cursor.execute('ALTER TABLE accounts ADD COLUMN custom_name TEXT')
            
            # Create indexes for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_user_id ON user_tokens(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_token_id ON accounts(token_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_accounts_custom_name ON accounts(custom_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_transaction_id ON transactions(transaction_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_category_primary ON transactions(category_primary)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_category_detailed ON transactions(category_detailed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)')
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash a password with salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        return password_hash.hex(), salt
    
    def create_user(self, username: str, password: str) -> Optional[int]:
        """Create a new user and return user ID"""
        try:
            password_hash, salt = self._hash_password(password)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, password_hash, salt)
                    VALUES (?, ?, ?)
                ''', (username, password_hash, salt))
                
                user_id = cursor.lastrowid
                conn.commit()
                return user_id
                
        except sqlite3.IntegrityError:
            return None  # Username already exists
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user info"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, password_hash, salt
                FROM users
                WHERE username = ?
            ''', (username,))
            
            user = cursor.fetchone()
            if not user:
                return None
            
            # Verify password
            password_hash, _ = self._hash_password(password, user['salt'])
            if password_hash == user['password_hash']:
                return {
                    'id': user['id'],
                    'username': user['username']
                }
            
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, created_at
                FROM users
                WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            if user:
                return dict(user)
            return None
    
    def store_user_token(self, user_id: int, access_token: str, item_id: Optional[str] = None, 
                         public_token: Optional[str] = None, institution_id: Optional[str] = None, 
                         institution_name: Optional[str] = None) -> bool:
        """Store a new access token with institution information (allows multiple per user)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if this specific item_id already exists for this user to avoid duplicates
                if item_id:
                    cursor.execute('SELECT id FROM user_tokens WHERE user_id = ? AND item_id = ?', 
                                 (user_id, item_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing token for this specific item
                        cursor.execute('''
                            UPDATE user_tokens
                            SET access_token = ?, public_token = ?, 
                                institution_id = ?, institution_name = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND item_id = ?
                        ''', (access_token, public_token, institution_id, institution_name, user_id, item_id))
                    else:
                        # Insert new token
                        cursor.execute('''
                            INSERT INTO user_tokens (user_id, access_token, item_id, public_token, 
                                                   institution_id, institution_name)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (user_id, access_token, item_id, public_token, institution_id, institution_name))
                else:
                    # Insert new token without item_id (fallback)
                    cursor.execute('''
                        INSERT INTO user_tokens (user_id, access_token, item_id, public_token, 
                                               institution_id, institution_name)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, access_token, item_id, public_token, institution_id, institution_name))
                
                conn.commit()
                return True
                
        except sqlite3.Error:
            return False
    
    def get_user_tokens(self, user_id: int) -> list[Dict[str, Any]]:
        """Get all user's access tokens with institution information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, access_token, item_id, public_token, institution_id, institution_name,
                       created_at, updated_at
                FROM user_tokens
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            
            tokens = cursor.fetchall()
            return [dict(token) for token in tokens]
    
    def get_user_token(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's first access token with institution information (for backward compatibility)"""
        tokens = self.get_user_tokens(user_id)
        return tokens[0] if tokens else None
    
    def delete_user_token(self, user_id: int, token_id: Optional[int] = None) -> bool:
        """Delete a specific user token or all tokens for user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if token_id:
                    cursor.execute('DELETE FROM user_tokens WHERE user_id = ? AND id = ?', 
                                 (user_id, token_id))
                else:
                    cursor.execute('DELETE FROM user_tokens WHERE user_id = ?', (user_id,))
                conn.commit()
                return True
        except sqlite3.Error:
            return False
    
    def get_all_users(self) -> list[Dict[str, Any]]:
        """Get all users (for admin purposes)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.created_at,
                       CASE WHEN ut.access_token IS NOT NULL THEN 1 ELSE 0 END as has_token
                FROM users u
                LEFT JOIN user_tokens ut ON u.id = ut.user_id
                ORDER BY u.created_at DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def store_accounts(self, user_id: int, token_id: int, accounts_data: list[Dict[str, Any]]) -> bool:
        """Store account information in the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for account in accounts_data:
                    # Use the classification provided by PlaidService, or fall back to our own logic
                    classification = account.get('account_classification')
                    
                    if not classification:
                        # Fallback classification logic if not provided
                        account_type = account.get('type', '').lower()
                        account_subtype = account.get('subtype', '').lower()
                        
                        if account_type in ['depository', 'investment', 'other']:
                            classification = 'asset'
                        elif account_type in ['credit', 'loan']:
                            classification = 'liability'
                        else:
                            # Default classification based on subtype
                            if account_subtype in ['checking', 'savings', 'money market', 'cd', 'brokerage', 'ira', '401k']:
                                classification = 'asset'
                            elif account_subtype in ['credit card', 'line of credit', 'mortgage', 'auto', 'student']:
                                classification = 'liability'
                            else:
                                classification = 'asset'  # Default to asset
                    
                    # Extract balance information
                    balances = account.get('balances', {})
                    current_balance = balances.get('current')
                    available_balance = balances.get('available')
                    
                    # Check if account already exists to preserve custom_name
                    cursor.execute('SELECT custom_name FROM accounts WHERE user_id = ? AND account_id = ?', 
                                 (user_id, account['account_id']))
                    existing_account = cursor.fetchone()
                    existing_custom_name = existing_account['custom_name'] if existing_account else None
                    
                    # Insert or update account
                    cursor.execute('''
                        INSERT OR REPLACE INTO accounts (
                            user_id, token_id, account_id, name, type, subtype, 
                            institution_name, current_balance, available_balance,
                            iso_currency_code, unofficial_currency_code, account_classification,
                            custom_name, is_active, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        user_id, token_id, account['account_id'], account['name'],
                        account['type'], account.get('subtype'), account.get('institution_name'),
                        current_balance, available_balance,
                        balances.get('iso_currency_code', 'USD'),
                        balances.get('unofficial_currency_code'),
                        classification, existing_custom_name, True
                    ))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            print(f"Error storing accounts: {e}")
            return False
    
    def get_cached_accounts(self, user_id: int) -> list[Dict[str, Any]]:
        """Get cached account information from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, ut.institution_name as token_institution_name
                FROM accounts a
                JOIN user_tokens ut ON a.token_id = ut.id
                WHERE a.user_id = ? AND a.is_active = 1
                ORDER BY a.institution_name, a.type, a.name
            ''', (user_id,))
            
            accounts = []
            for row in cursor.fetchall():
                account_dict = dict(row)
                # Format the account data to match Plaid API structure
                formatted_account = {
                    'account_id': account_dict['account_id'],
                    'name': account_dict['name'],
                    'type': account_dict['type'],
                    'subtype': account_dict['subtype'],
                    'balances': {
                        'current': account_dict['current_balance'],
                        'available': account_dict['available_balance'],
                        'iso_currency_code': account_dict['iso_currency_code'],
                        'unofficial_currency_code': account_dict['unofficial_currency_code']
                    },
                    'institution_name': account_dict['institution_name'],
                    'token_id': account_dict['token_id'],
                    'account_classification': account_dict['account_classification'],
                    'custom_name': account_dict['custom_name'],
                    'display_name': account_dict['custom_name'] if account_dict['custom_name'] else account_dict['name'],
                    'updated_at': account_dict['updated_at'],
                    'formatted_balance': f"${account_dict['current_balance']:,.2f}" if account_dict['current_balance'] is not None else "N/A"
                }
                accounts.append(formatted_account)
            
            return accounts
    
    def update_account_balances(self, user_id: int, accounts_data: list[Dict[str, Any]]) -> bool:
        """Update account balances from fresh API data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for account in accounts_data:
                    balances = account.get('balances', {})
                    cursor.execute('''
                        UPDATE accounts 
                        SET current_balance = ?, available_balance = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND account_id = ?
                    ''', (
                        balances.get('current'),
                        balances.get('available'),
                        user_id,
                        account['account_id']
                    ))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            print(f"Error updating account balances: {e}")
            return False
    
    def delete_accounts_by_token(self, user_id: int, token_id: int) -> bool:
        """Delete accounts associated with a specific token"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM accounts WHERE user_id = ? AND token_id = ?', 
                             (user_id, token_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error deleting accounts: {e}")
            return False
    
    def get_account_summary(self, user_id: int) -> Dict[str, Any]:
        """Get summary statistics for user's accounts"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get totals by classification
            cursor.execute('''
                SELECT 
                    account_classification,
                    COUNT(*) as count,
                    SUM(current_balance) as total_balance
                FROM accounts 
                WHERE user_id = ? AND is_active = 1 AND current_balance IS NOT NULL
                GROUP BY account_classification
            ''', (user_id,))
            
            classification_summary = {}
            for row in cursor.fetchall():
                classification_summary[row['account_classification']] = {
                    'count': row['count'],
                    'total_balance': row['total_balance']
                }
            
            # Get totals by account type
            cursor.execute('''
                SELECT 
                    type,
                    COUNT(*) as count,
                    SUM(current_balance) as total_balance
                FROM accounts 
                WHERE user_id = ? AND is_active = 1 AND current_balance IS NOT NULL
                GROUP BY type
            ''', (user_id,))
            
            type_summary = {}
            for row in cursor.fetchall():
                type_summary[row['type']] = {
                    'count': row['count'],
                    'total_balance': row['total_balance']
                }
            
            return {
                'by_classification': classification_summary,
                'by_type': type_summary,
                'net_worth': (classification_summary.get('asset', {}).get('total_balance', 0) - 
                            classification_summary.get('liability', {}).get('total_balance', 0))
            }
    
    def update_account_custom_name(self, user_id: int, account_id: str, custom_name: Optional[str]) -> bool:
        """Update the custom name for an account"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Trim whitespace and convert empty string to None
                custom_name = custom_name.strip() if custom_name else None
                if custom_name == '':
                    custom_name = None
                
                cursor.execute('''
                    UPDATE accounts 
                    SET custom_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND account_id = ?
                ''', (custom_name, user_id, account_id))
                
                # Check if any rows were updated
                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    return False
                    
        except sqlite3.Error as e:
            print(f"Error updating account custom name: {e}")
            return False
    
    def store_transactions(self, user_id: int, transactions_data: list[Dict[str, Any]]) -> bool:
        """Store transaction information in the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for transaction in transactions_data:
                    # Extract transaction data
                    transaction_id = transaction.get('transaction_id')
                    account_id = transaction.get('account_id')
                    amount = transaction.get('amount')
                    date = transaction.get('date')
                    name = transaction.get('name')
                    
                    # Extract category information
                    category = None
                    subcategory = None
                    categories = transaction.get('category', [])
                    if categories:
                        category = categories[0] if len(categories) > 0 else None
                        subcategory = categories[1] if len(categories) > 1 else None
                    
                    # Insert or update transaction
                    cursor.execute('''
                        INSERT OR REPLACE INTO transactions (
                            user_id, account_id, transaction_id, amount, iso_currency_code,
                            unofficial_currency_code, date, datetime, authorized_date,
                            authorized_datetime, name, merchant_name, account_owner,
                            category, subcategory, transaction_type, pending,
                            institution_name, category_primary, category_detailed,
                            category_confidence, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        user_id, account_id, transaction_id, amount,
                        transaction.get('iso_currency_code', 'USD'),
                        transaction.get('unofficial_currency_code'),
                        date, transaction.get('datetime'),
                        transaction.get('authorized_date'),
                        transaction.get('authorized_datetime'),
                        name, transaction.get('merchant_name'),
                        transaction.get('account_owner'),
                        category, subcategory,
                        transaction.get('transaction_type'),
                        transaction.get('pending', False),
                        transaction.get('institution_name'),
                        transaction.get('category_primary', 'OTHER'),
                        transaction.get('category_detailed', 'OTHER'),
                        transaction.get('category_confidence', 'UNKNOWN')
                    ))
                
                conn.commit()
                return True
                
        except sqlite3.Error as e:
            print(f"Error storing transactions: {e}")
            return False
    
    def get_cached_transactions(self, user_id: int, account_types: Optional[list[str]] = None, 
                              account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, limit: int = 100, offset: int = 0) -> list[Dict[str, Any]]:
        """Get cached transaction information from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query with optional account type filtering and account ID filtering
            query = '''
                SELECT t.*, a.name as account_name, a.type as account_type, 
                       a.subtype as account_subtype, a.institution_name
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = ? AND a.is_active = 1
            '''
            params: list[Any] = [user_id]
            
            # Add year/month filtering
            if year is not None:
                if month is not None:
                    # Specific month
                    query += ' AND strftime("%Y", t.date) = ? AND strftime("%m", t.date) = ?'
                    params.extend([str(year), f"{month:02d}"])
                else:
                    # Entire year
                    query += ' AND strftime("%Y", t.date) = ?'
                    params.append(str(year))
            
            if account_id:
                query += ' AND t.account_id = ?'
                params.append(account_id)
            elif account_types:
                placeholders = ','.join(['?' for _ in account_types])
                query += f' AND a.type IN ({placeholders})'
                params.extend(account_types)
            
            query += ' ORDER BY t.date DESC, t.datetime DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            
            transactions = []
            for row in cursor.fetchall():
                transaction_dict = dict(row)
                # Format the transaction data
                formatted_transaction = {
                    'transaction_id': transaction_dict['transaction_id'],
                    'account_id': transaction_dict['account_id'],
                    'account_name': transaction_dict['account_name'],
                    'account_type': transaction_dict['account_type'],
                    'account_subtype': transaction_dict['account_subtype'],
                    'amount': transaction_dict['amount'],
                    'name': transaction_dict['name'],
                    'merchant_name': transaction_dict['merchant_name'],
                    'category': transaction_dict['category'],
                    'subcategory': transaction_dict['subcategory'],
                    'category_primary': transaction_dict.get('category_primary', 'OTHER'),
                    'category_detailed': transaction_dict.get('category_detailed', 'OTHER'),
                    'category_confidence': transaction_dict.get('category_confidence', 'UNKNOWN'),
                    'date': transaction_dict['date'],
                    'pending': transaction_dict['pending'],
                    'institution_name': transaction_dict['institution_name'],
                    'formatted_amount': f"${abs(transaction_dict['amount']):,.2f}",
                    'transaction_type': 'debit' if transaction_dict['amount'] > 0 else 'credit',
                    'updated_at': transaction_dict['updated_at']
                }
                transactions.append(formatted_transaction)
            
            return transactions
    
    def get_transaction_summary(self, user_id: int, account_types: Optional[list[str]] = None, 
                              account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """Get transaction summary statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query with optional account type filtering and account ID filtering
            query = '''
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as total_debits,
                    SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as total_credits,
                    AVG(ABS(t.amount)) as avg_transaction_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = ? AND a.is_active = 1
            '''
            
            params: list[Any] = [user_id]
            
            # Add year/month filtering
            if year is not None:
                if month is not None:
                    # Specific month
                    query += ' AND strftime("%Y", t.date) = ? AND strftime("%m", t.date) = ?'
                    params.extend([str(year), f"{month:02d}"])
                else:
                    # Entire year
                    query += ' AND strftime("%Y", t.date) = ?'
                    params.append(str(year))
            
            if account_id:
                query += ' AND t.account_id = ?'
                params.append(account_id)
            elif account_types:
                placeholders = ','.join(['?' for _ in account_types])
                query += f' AND a.type IN ({placeholders})'
                params.extend(account_types)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            # Get spending by category (old category field for backward compatibility)
            category_query = '''
                SELECT 
                    t.category,
                    COUNT(*) as transaction_count,
                    SUM(ABS(t.amount)) as total_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = ? AND a.is_active = 1
                AND t.category IS NOT NULL
            '''
            
            # Add year/month filtering to category query
            if year is not None:
                if month is not None:
                    # Specific month
                    category_query += ' AND strftime("%Y", t.date) = ? AND strftime("%m", t.date) = ?'
                else:
                    # Entire year
                    category_query += ' AND strftime("%Y", t.date) = ?'
            
            if account_id:
                category_query += ' AND t.account_id = ?'
            elif account_types:
                placeholders = ','.join(['?' for _ in account_types])
                category_query += f' AND a.type IN ({placeholders})'
            
            category_query += ' GROUP BY t.category ORDER BY total_amount DESC LIMIT 10'
            
            cursor.execute(category_query, params)
            categories = []
            for cat_row in cursor.fetchall():
                categories.append({
                    'category': cat_row['category'],
                    'transaction_count': cat_row['transaction_count'],
                    'total_amount': cat_row['total_amount']
                })
            
            # Get spending by primary category (new Plaid categorization)
            primary_category_query = '''
                SELECT 
                    t.category_primary,
                    COUNT(*) as transaction_count,
                    SUM(ABS(t.amount)) as total_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = ? AND a.is_active = 1
                AND t.category_primary IS NOT NULL
                AND t.category_primary != 'OTHER'
            '''
            
            # Add year/month filtering to primary category query
            if year is not None:
                if month is not None:
                    # Specific month
                    primary_category_query += ' AND strftime("%Y", t.date) = ? AND strftime("%m", t.date) = ?'
                else:
                    # Entire year
                    primary_category_query += ' AND strftime("%Y", t.date) = ?'
            
            if account_id:
                primary_category_query += ' AND t.account_id = ?'
            elif account_types:
                placeholders = ','.join(['?' for _ in account_types])
                primary_category_query += f' AND a.type IN ({placeholders})'
            
            primary_category_query += ' GROUP BY t.category_primary ORDER BY total_amount DESC LIMIT 10'
            
            cursor.execute(primary_category_query, params)
            primary_categories = []
            for cat_row in cursor.fetchall():
                primary_categories.append({
                    'category': cat_row['category_primary'],
                    'transaction_count': cat_row['transaction_count'],
                    'total_amount': cat_row['total_amount']
                })
            
            # Calculate period days
            if year is not None and month is not None:
                # Specific month - calculate days in that month
                import calendar
                days = calendar.monthrange(year, month)[1]
            elif year is not None:
                # Entire year - 365 or 366 days
                days = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
            else:
                # Default to 30 days
                days = 30
            
            return {
                'total_transactions': row['total_transactions'] or 0,
                'total_debits': row['total_debits'] or 0,
                'total_credits': row['total_credits'] or 0,
                'avg_transaction_amount': row['avg_transaction_amount'] or 0,
                'net_flow': (row['total_debits'] or 0) - (row['total_credits'] or 0),
                'top_categories': categories,
                'top_primary_categories': primary_categories,
                'period_days': days
            }
    
    def delete_transactions_by_account(self, user_id: int, account_id: str) -> bool:
        """Delete transactions for a specific account"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM transactions WHERE user_id = ? AND account_id = ?', 
                             (user_id, account_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error deleting transactions: {e}")
            return False 