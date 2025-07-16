from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from plaid_budget_fetcher import PlaidService
from database import DatabaseManager
from dotenv import load_dotenv
import os
from functools import wraps

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize services
plaid_service = None
db = None

def get_plaid_service():
    global plaid_service
    if plaid_service is None:
        client_id = os.getenv('PLAID_CLIENT_ID')
        secret = os.getenv('PLAID_SECRET')
        environment = os.getenv('PLAID_ENV', 'sandbox')
        
        if not client_id or not secret:
            raise ValueError("Missing PLAID_CLIENT_ID or PLAID_SECRET environment variables")
        
        plaid_service = PlaidService(
            client_id=client_id,
            secret=secret,
            environment=environment
        )
    return plaid_service

def get_db():
    global db
    if db is None:
        db = DatabaseManager()
    return db

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def main():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        has_token = service.has_access_token(user_id)
        
        # Get user info
        user = get_db().get_user_by_id(user_id)
        
        # Get token info including institution (for backward compatibility)
        token_info = None
        accounts_data = None
        accounts_error = None
        institutions_count = 0
        account_summary = None
        is_cached = False
        
        if has_token:
            token_info = get_db().get_user_token(user_id)
            institutions_count = service.get_institutions_count(user_id)
            
            # Check if user requested refresh
            force_refresh = request.args.get('refresh') == 'true'
            
            # Try to fetch account information (cached by default)
            try:
                accounts_data = service.get_accounts(user_id, force_refresh=force_refresh)
                is_cached = accounts_data.get('is_cached', False)
                
                # Handle any errors from individual institutions
                if accounts_data.get('errors'):
                    accounts_error = "; ".join(accounts_data['errors'])
                
                # Balances are now formatted in the database, no need to format here
                
                # If no accounts found but no errors, show info message
                if not accounts_data.get('accounts') and not accounts_data.get('errors'):
                    accounts_error = "No accounts found from connected institutions"
                
                # Get account summary
                account_summary = get_db().get_account_summary(user_id)
                    
            except Exception as e:
                accounts_error = f"Failed to fetch accounts: {str(e)}"
                is_cached = False
        
        return render_template('home.html', 
                             has_token=has_token,
                             environment=service.environment,
                             user=user,
                             token_info=token_info,
                             accounts_data=accounts_data,
                             accounts_error=accounts_error,
                             institutions_count=institutions_count,
                             account_summary=account_summary,
                             is_cached=is_cached)
    except Exception as e:
        return render_template('home.html', 
                             error=str(e),
                             user=None,
                             token_info=None,
                             accounts_data=None,
                             accounts_error=None,
                             institutions_count=0,
                             account_summary=None,
                             is_cached=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')
        
        try:
            user = get_db().authenticate_user(username, password)
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect(url_for('main'))
            else:
                flash('Invalid username or password.', 'error')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')
        
        try:
            user_id = get_db().create_user(username, password)
            if user_id:
                session['user_id'] = user_id
                session['username'] = username
                flash(f'Registration successful! Welcome, {username}!', 'success')
                return redirect(url_for('main'))
            else:
                flash('Username already exists. Please choose a different one.', 'error')
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'success')
    return redirect(url_for('login'))

@app.route('/exchange_token', methods=['POST'])
@login_required
def exchange_token():
    """Exchange public token for access token"""
    if 'public_token' not in request.form:
        if request.content_type == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({"error": "public_token is required"}), 400
        else:
            flash("Public token is required", "error")
            return redirect(url_for('main'))
    
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        public_token = request.form['public_token']
        
        result = service.exchange_public_token(public_token, user_id)
        
        # Check if this is a form submission (web) or API call
        if request.content_type == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify(result)
        else:
            flash("Access token obtained successfully!", "success")
            return redirect(url_for('main'))
            
    except Exception as e:
        if request.content_type == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({"error": str(e)}), 500
        else:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('main'))

@app.route('/accounts', methods=['GET'])
@login_required
def get_accounts():
    """Get user accounts (supports refresh parameter)"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        if not service.has_access_token(user_id):
            return jsonify({"error": "No access token. Please connect a bank account first."}), 400
        
        # Check if user requested refresh
        force_refresh = request.args.get('refresh') == 'true'
        
        accounts = service.get_accounts(user_id, force_refresh=force_refresh)
        return jsonify(accounts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    """Get user transactions (supports filtering and refresh)"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        if not service.has_access_token(user_id):
            return jsonify({"error": "No access token. Please connect a bank account first."}), 400
        
        # Get query parameters
        account_types = request.args.getlist('account_types')  # e.g., ?account_types=depository&account_types=credit
        days = int(request.args.get('days', 30))
        year = request.args.get('year')
        month = request.args.get('month')
        force_refresh = request.args.get('refresh') == 'true'
        
        # Default to checking and credit card accounts if no filter specified
        if not account_types:
            account_types = ['depository', 'credit']
        
        # Convert string parameters to integers if provided and not empty
        year_int = None
        month_int = None
        
        if year and year.strip():
            year_int = int(year)
        if month and month.strip():
            month_int = int(month)
        
        # If no explicit year/month provided, but days is provided, use current date logic
        if year_int is None and month_int is None and days:
            from datetime import datetime
            current_date = datetime.now()
            year_int = current_date.year
            # For days-based filtering, use current month
            month_int = current_date.month
        
        transactions = service.get_transactions(
            user_id, 
            account_types=account_types,
            year=year_int if year_int is not None else None,
            month=month_int if month_int is not None else None,
            force_refresh=force_refresh
        )
        return jsonify(transactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/checking')
@login_required
def get_checking_transactions():
    """Get transactions from checking accounts only"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        if not service.has_access_token(user_id):
            return jsonify({"error": "No access token. Please connect a bank account first."}), 400
        
        # Get query parameters
        days = int(request.args.get('days', 30))
        year = request.args.get('year')
        month = request.args.get('month')
        force_refresh = request.args.get('refresh') == 'true'
        
        # Convert string parameters to integers if provided and not empty
        year_int = None
        month_int = None
        
        if year and year.strip():
            year_int = int(year)
        if month and month.strip():
            month_int = int(month)
        
        # If no explicit year/month provided, but days is provided, use current date logic
        if year_int is None and month_int is None and days:
            from datetime import datetime
            current_date = datetime.now()
            year_int = current_date.year
            # For days-based filtering, use current month
            month_int = current_date.month
        
        transactions = service.get_transactions(
            user_id, 
            account_types=['depository'],
            year=year_int,
            month=month_int,
            force_refresh=force_refresh
        )
        return jsonify(transactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/credit')
@login_required
def get_credit_transactions():
    """Get transactions from credit card accounts only"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        if not service.has_access_token(user_id):
            return jsonify({"error": "No access token. Please connect a bank account first."}), 400
        
        # Get query parameters
        days = int(request.args.get('days', 30))
        year = request.args.get('year')
        month = request.args.get('month')
        force_refresh = request.args.get('refresh') == 'true'
        
        # Convert string parameters to integers if provided and not empty
        year_int = None
        month_int = None
        
        if year and year.strip():
            year_int = int(year)
        if month and month.strip():
            month_int = int(month)
        
        # If no explicit year/month provided, but days is provided, use current date logic
        if year_int is None and month_int is None and days:
            from datetime import datetime
            current_date = datetime.now()
            year_int = current_date.year
            # For days-based filtering, use current month
            month_int = current_date.month
        
        transactions = service.get_transactions(
            user_id, 
            account_types=['credit'],
            year=year_int,
            month=month_int,
            force_refresh=force_refresh
        )
        return jsonify(transactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/transactions/page')
@login_required
def transactions_page():
    """Render the transactions page"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        if not service.has_access_token(user_id):
            flash("Please connect a bank account first.", "error")
            return redirect(url_for('main'))
        
        # Get user info
        user = get_db().get_user_by_id(user_id)
        
        # Get basic account info for filtering
        accounts_data = service.get_cached_accounts(user_id)
        
        # Get cached transactions for initial display
        transactions_data = service.get_cached_transactions(user_id, ['depository', 'credit'])
        
        return render_template('transactions.html',
                             user=user,
                             accounts_data=accounts_data,
                             transactions_data=transactions_data,
                             environment=service.environment)
    except Exception as e:
        flash(f"Error loading transactions: {str(e)}", "error")
        return redirect(url_for('main'))

@app.route('/status', methods=['GET'])
@login_required
def status():
    """Check service status and token availability"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        
        return jsonify({
            "service_initialized": True,
            "has_access_token": service.has_access_token(user_id),
            "environment": service.environment,
            "user_id": user_id,
            "username": session.get('username')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create_token')
@login_required
def create_token():
    """Render the Plaid Link page for creating public tokens"""
    try:
        service = get_plaid_service()
        return render_template('plaid_link.html', environment=service.environment)
    except Exception as e:
        flash(f"Error initializing Plaid Link: {str(e)}", "error")
        return redirect(url_for('main'))

@app.route('/create_link_token', methods=['POST'])
@login_required
def create_link_token():
    """Create a link token for Plaid Link"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        result = service.create_link_token(user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/store_public_token', methods=['POST'])
@login_required
def store_public_token():
    """Store public token and automatically exchange it for access token"""
    try:
        data = request.get_json()
        public_token = data.get('public_token')
        metadata = data.get('metadata', {})
        user_id = session['user_id']
        
        if not public_token:
            return jsonify({"error": "Public token is required"}), 400
        
        # Automatically exchange public token for access token
        service = get_plaid_service()
        exchange_result = service.exchange_public_token(public_token, user_id)
        
        # Extract institution information from metadata
        institution_name = metadata.get('institution', {}).get('name', 'Unknown Institution')
        accounts_count = len(metadata.get('accounts', []))
        
        return jsonify({
            "success": True,
            "message": "Account connected successfully!",
            "access_token_obtained": True,
            "institution_name": institution_name,
            "accounts_count": accounts_count,
            "item_id": exchange_result.get('item_id'),
            "user_id": user_id
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "success": False,
            "message": "Failed to connect account"
        }), 500

@app.route('/revoke_token', methods=['POST'])
@login_required
def revoke_token():
    """Revoke user's access token(s)"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        token_id = request.form.get('token_id')  # Optional: specific token to revoke
        
        if token_id:
            success = service.revoke_access_token(user_id, int(token_id))
            if success:
                flash("Bank connection removed successfully!", "success")
            else:
                flash("Failed to remove bank connection.", "error")
        else:
            success = service.revoke_access_token(user_id)
            if success:
                flash("All access tokens revoked successfully!", "success")
            else:
                flash("Failed to revoke access tokens.", "error")
        
        return redirect(url_for('main'))
    except Exception as e:
        flash(f"Error revoking token: {str(e)}", "error")
        return redirect(url_for('main'))

@app.route('/add_account')
@login_required
def add_account():
    """Render the Plaid Link page for adding additional accounts"""
    try:
        service = get_plaid_service()
        user_id = session['user_id']
        institutions_count = service.get_institutions_count(user_id)
        
        return render_template('plaid_link.html', 
                             environment=service.environment,
                             is_additional_account=True,
                             institutions_count=institutions_count)
    except Exception as e:
        flash(f"Error initializing Plaid Link: {str(e)}", "error")
        return redirect(url_for('main'))

if __name__ == '__main__':
    app.run(debug=True) 