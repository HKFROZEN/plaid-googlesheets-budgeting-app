import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import secrets
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages PostgreSQL database operations for user authentication and token storage"""
    
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        if db_config is None:
            self.db_config = {
                'host': os.getenv('POSTGRES_HOST', 'localhost'),
                'port': int(os.getenv('POSTGRES_PORT', 5432)),
                'database': os.getenv('POSTGRES_DB', 'plaid_budgeting_app'),
                'user': os.getenv('POSTGRES_USER', 'postgres'),
                'password': os.getenv('POSTGRES_PASSWORD', '')
            }
        else:
            self.db_config = db_config
        
        self.test_connection()
    
    def test_connection(self):
        """Test PostgreSQL connection on initialization"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                logger.info("PostgreSQL connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(**self.db_config)
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
                    VALUES (%s, %s, %s)
                    RETURNING id
                ''', (username, password_hash, salt))
                
                user_id = cursor.fetchone()[0]
                conn.commit()
                return user_id
                
        except psycopg2.IntegrityError:
            return None  # Username already exists
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user and return user info"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT id, username, password_hash, salt
                FROM users
                WHERE username = %s
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
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT id, username, created_at
                FROM users
                WHERE id = %s
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
                    cursor.execute('SELECT id FROM user_tokens WHERE user_id = %s AND item_id = %s', 
                                 (user_id, item_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing token for this specific item
                        cursor.execute('''
                            UPDATE user_tokens
                            SET access_token = %s, public_token = %s, 
                                institution_id = %s, institution_name = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = %s AND item_id = %s
                        ''', (access_token, public_token, institution_id, institution_name, user_id, item_id))
                    else:
                        # Insert new token
                        cursor.execute('''
                            INSERT INTO user_tokens (user_id, access_token, item_id, public_token, 
                                                   institution_id, institution_name)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        ''', (user_id, access_token, item_id, public_token, institution_id, institution_name))
                else:
                    # Insert new token without item_id (fallback)
                    cursor.execute('''
                        INSERT INTO user_tokens (user_id, access_token, item_id, public_token, 
                                               institution_id, institution_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (user_id, access_token, item_id, public_token, institution_id, institution_name))
                
                conn.commit()
                return True
                
        except psycopg2.Error:
            return False
    
    def get_user_tokens(self, user_id: int) -> list[Dict[str, Any]]:
        """Get all user's access tokens with institution information"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT id, access_token, item_id, public_token, institution_id, institution_name,
                       created_at, updated_at
                FROM user_tokens
                WHERE user_id = %s
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
                    cursor.execute('DELETE FROM user_tokens WHERE user_id = %s AND id = %s', 
                                 (user_id, token_id))
                else:
                    cursor.execute('DELETE FROM user_tokens WHERE user_id = %s', (user_id,))
                conn.commit()
                return True
        except psycopg2.Error:
            return False
    
    def get_all_users(self) -> list[Dict[str, Any]]:
        """Get all users (for admin purposes)"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
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
                    
                    # Insert or update account
                    cursor.execute('''
                        INSERT INTO accounts (
                            user_id, token_id, account_id, name, type, subtype, 
                            institution_name, current_balance, available_balance,
                            iso_currency_code, unofficial_currency_code, account_classification,
                            is_active, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id, account_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            type = EXCLUDED.type,
                            subtype = EXCLUDED.subtype,
                            institution_name = EXCLUDED.institution_name,
                            current_balance = EXCLUDED.current_balance,
                            available_balance = EXCLUDED.available_balance,
                            iso_currency_code = EXCLUDED.iso_currency_code,
                            unofficial_currency_code = EXCLUDED.unofficial_currency_code,
                            account_classification = EXCLUDED.account_classification,
                            is_active = EXCLUDED.is_active,
                            updated_at = CURRENT_TIMESTAMP
                    ''', (
                        user_id, token_id, account['account_id'], account['name'],
                        account['type'], account.get('subtype'), account.get('institution_name'),
                        current_balance, available_balance,
                        balances.get('iso_currency_code', 'USD'),
                        balances.get('unofficial_currency_code'),
                        classification, True
                    ))
                
                conn.commit()
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Error storing accounts: {e}")
            return False
    
    def get_cached_accounts(self, user_id: int) -> list[Dict[str, Any]]:
        """Get cached account information from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('''
                SELECT a.*, ut.institution_name as token_institution_name
                FROM accounts a
                JOIN user_tokens ut ON a.token_id = ut.id
                WHERE a.user_id = %s AND a.is_active = TRUE
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
                        'current': float(account_dict['current_balance']) if account_dict['current_balance'] is not None else None,
                        'available': float(account_dict['available_balance']) if account_dict['available_balance'] is not None else None,
                        'iso_currency_code': account_dict['iso_currency_code'],
                        'unofficial_currency_code': account_dict['unofficial_currency_code']
                    },
                    'institution_name': account_dict['institution_name'],
                    'token_id': account_dict['token_id'],
                    'account_classification': account_dict['account_classification'],
                    'updated_at': account_dict['updated_at'],
                    'formatted_balance': f"${float(account_dict['current_balance']):,.2f}" if account_dict['current_balance'] is not None else "N/A"
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
                        SET current_balance = %s, available_balance = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND account_id = %s
                    ''', (
                        balances.get('current'),
                        balances.get('available'),
                        user_id,
                        account['account_id']
                    ))
                
                conn.commit()
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Error updating account balances: {e}")
            return False
    
    def delete_accounts_by_token(self, user_id: int, token_id: int) -> bool:
        """Delete accounts associated with a specific token"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM accounts WHERE user_id = %s AND token_id = %s', 
                             (user_id, token_id))
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Error deleting accounts: {e}")
            return False
    
    def get_account_summary(self, user_id: int) -> Dict[str, Any]:
        """Get summary statistics for user's accounts"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get totals by classification
            cursor.execute('''
                SELECT 
                    account_classification,
                    COUNT(*) as count,
                    SUM(current_balance) as total_balance
                FROM accounts 
                WHERE user_id = %s AND is_active = TRUE AND current_balance IS NOT NULL
                GROUP BY account_classification
            ''', (user_id,))
            
            classification_summary = {}
            for row in cursor.fetchall():
                classification_summary[row['account_classification']] = {
                    'count': row['count'],
                    'total_balance': float(row['total_balance'])
                }
            
            # Get totals by account type
            cursor.execute('''
                SELECT 
                    type,
                    COUNT(*) as count,
                    SUM(current_balance) as total_balance
                FROM accounts 
                WHERE user_id = %s AND is_active = TRUE AND current_balance IS NOT NULL
                GROUP BY type
            ''', (user_id,))
            
            type_summary = {}
            for row in cursor.fetchall():
                type_summary[row['type']] = {
                    'count': row['count'],
                    'total_balance': float(row['total_balance'])
                }
            
            return {
                'by_classification': classification_summary,
                'by_type': type_summary,
                'net_worth': (classification_summary.get('asset', {}).get('total_balance', 0) - 
                            classification_summary.get('liability', {}).get('total_balance', 0))
            }
    
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
                        INSERT INTO transactions (
                            user_id, account_id, transaction_id, amount, iso_currency_code,
                            unofficial_currency_code, date, datetime, authorized_date,
                            authorized_datetime, name, merchant_name, account_owner,
                            category, subcategory, transaction_type, pending,
                            institution_name, category_primary, category_detailed,
                            category_confidence, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id, transaction_id) DO UPDATE SET
                            amount = EXCLUDED.amount,
                            iso_currency_code = EXCLUDED.iso_currency_code,
                            unofficial_currency_code = EXCLUDED.unofficial_currency_code,
                            date = EXCLUDED.date,
                            datetime = EXCLUDED.datetime,
                            authorized_date = EXCLUDED.authorized_date,
                            authorized_datetime = EXCLUDED.authorized_datetime,
                            name = EXCLUDED.name,
                            merchant_name = EXCLUDED.merchant_name,
                            account_owner = EXCLUDED.account_owner,
                            category = EXCLUDED.category,
                            subcategory = EXCLUDED.subcategory,
                            transaction_type = EXCLUDED.transaction_type,
                            pending = EXCLUDED.pending,
                            institution_name = EXCLUDED.institution_name,
                            category_primary = EXCLUDED.category_primary,
                            category_detailed = EXCLUDED.category_detailed,
                            category_confidence = EXCLUDED.category_confidence,
                            updated_at = CURRENT_TIMESTAMP
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
                
        except psycopg2.Error as e:
            logger.error(f"Error storing transactions: {e}")
            return False
    
    def get_cached_transactions(self, user_id: int, account_types: Optional[list[str]] = None, 
                              account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, limit: int = 100, offset: int = 0) -> list[Dict[str, Any]]:
        """Get cached transaction information from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query with optional account type filtering and account ID filtering
            query = '''
                SELECT t.*, a.name as account_name, a.type as account_type, 
                       a.subtype as account_subtype, a.institution_name
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = %s AND a.is_active = TRUE
            '''
            params: list[Any] = [user_id]
            
            # Add year/month filtering
            if year is not None:
                if month is not None:
                    # Specific month
                    query += ' AND EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s'
                    params.extend([year, month])
                else:
                    # Entire year
                    query += ' AND EXTRACT(YEAR FROM t.date) = %s'
                    params.append(year)
            
            if account_id:
                query += ' AND t.account_id = %s'
                params.append(account_id)
            elif account_types:
                placeholders = ','.join(['%s' for _ in account_types])
                query += f' AND a.type IN ({placeholders})'
                params.extend(account_types)
            
            query += ' ORDER BY t.date DESC, t.datetime DESC LIMIT %s OFFSET %s'
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
                    'amount': float(transaction_dict['amount']),
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
                    'formatted_amount': f"${abs(float(transaction_dict['amount'])):,.2f}",
                    'transaction_type': 'debit' if float(transaction_dict['amount']) > 0 else 'credit',
                    'updated_at': transaction_dict['updated_at']
                }
                transactions.append(formatted_transaction)
            
            return transactions
    
    def get_transaction_summary(self, user_id: int, account_types: Optional[list[str]] = None, 
                              account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """Get transaction summary statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query with optional account type filtering and account ID filtering
            query = '''
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as total_debits,
                    SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as total_credits,
                    AVG(ABS(t.amount)) as avg_transaction_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = %s AND a.is_active = TRUE
            '''
            
            params: list[Any] = [user_id]
            
            # Add year/month filtering
            if year is not None:
                if month is not None:
                    # Specific month
                    query += ' AND EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s'
                    params.extend([year, month])
                else:
                    # Entire year
                    query += ' AND EXTRACT(YEAR FROM t.date) = %s'
                    params.append(year)
            
            if account_id:
                query += ' AND t.account_id = %s'
                params.append(account_id)
            elif account_types:
                placeholders = ','.join(['%s' for _ in account_types])
                query += f' AND a.type IN ({placeholders})'
                params.extend(account_types)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            # Get spending by category
            category_query = '''
                SELECT 
                    t.category,
                    COUNT(*) as transaction_count,
                    SUM(ABS(t.amount)) as total_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = %s AND a.is_active = TRUE
                AND t.category IS NOT NULL
            '''
            
            # Add year/month filtering to category query
            if year is not None:
                if month is not None:
                    # Specific month
                    category_query += ' AND EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s'
                else:
                    # Entire year
                    category_query += ' AND EXTRACT(YEAR FROM t.date) = %s'
            
            if account_id:
                category_query += ' AND t.account_id = %s'
            elif account_types:
                placeholders = ','.join(['%s' for _ in account_types])
                category_query += f' AND a.type IN ({placeholders})'
            
            category_query += ' GROUP BY t.category ORDER BY total_amount DESC LIMIT 10'
            
            cursor.execute(category_query, params)
            categories = []
            for cat_row in cursor.fetchall():
                categories.append({
                    'category': cat_row['category'],
                    'transaction_count': cat_row['transaction_count'],
                    'total_amount': float(cat_row['total_amount'])
                })
            
            # Get spending by primary category (new Plaid categorization)
            primary_category_query = '''
                SELECT 
                    t.category_primary,
                    COUNT(*) as transaction_count,
                    SUM(ABS(t.amount)) as total_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id AND t.user_id = a.user_id
                WHERE t.user_id = %s AND a.is_active = TRUE
                AND t.category_primary IS NOT NULL
                AND t.category_primary != 'OTHER'
            '''
            
            # Add year/month filtering to primary category query
            if year is not None:
                if month is not None:
                    # Specific month
                    primary_category_query += ' AND EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s'
                else:
                    # Entire year
                    primary_category_query += ' AND EXTRACT(YEAR FROM t.date) = %s'
            
            if account_id:
                primary_category_query += ' AND t.account_id = %s'
            elif account_types:
                placeholders = ','.join(['%s' for _ in account_types])
                primary_category_query += f' AND a.type IN ({placeholders})'
            
            primary_category_query += ' GROUP BY t.category_primary ORDER BY total_amount DESC LIMIT 10'
            
            cursor.execute(primary_category_query, params)
            primary_categories = []
            for cat_row in cursor.fetchall():
                primary_categories.append({
                    'category': cat_row['category_primary'],
                    'transaction_count': cat_row['transaction_count'],
                    'total_amount': float(cat_row['total_amount'])
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
                'total_debits': float(row['total_debits']) if row['total_debits'] else 0,
                'total_credits': float(row['total_credits']) if row['total_credits'] else 0,
                'avg_transaction_amount': float(row['avg_transaction_amount']) if row['avg_transaction_amount'] else 0,
                'net_flow': (float(row['total_debits']) if row['total_debits'] else 0) - (float(row['total_credits']) if row['total_credits'] else 0),
                'top_categories': categories,
                'top_primary_categories': primary_categories,
                'period_days': days
            }
    
    def delete_transactions_by_account(self, user_id: int, account_id: str) -> bool:
        """Delete transactions for a specific account"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM transactions WHERE user_id = %s AND account_id = %s', 
                             (user_id, account_id))
                conn.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Error deleting transactions: {e}")
            return False 