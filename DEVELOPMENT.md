# Development Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git
- Plaid Developer Account (https://dashboard.plaid.com/)

## Environment Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd plaid-googlesheets-budgeting-app
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory with the following variables:
   ```env
   SECRET_KEY=your-secret-key-here-change-in-production
   FLASK_ENV=development
   FLASK_DEBUG=1
   PLAID_CLIENT_ID=your-plaid-client-id
   PLAID_SECRET=your-plaid-secret-key
   PLAID_ENV=sandbox
   ```

## Plaid Configuration

1. **Create a Plaid Developer Account:**
   - Go to https://dashboard.plaid.com/
   - Sign up for a free developer account
   - Create a new application

2. **Get your API credentials:**
   - Navigate to your app's settings
   - Copy your `client_id` and `secret` keys
   - Use `sandbox` environment for development

3. **Configure allowed products:**
   - Enable "Transactions" product
   - Enable "Accounts" product
   - Configure redirect URIs if needed

## Running the Application

1. **Start the development server:**
   ```bash
   python app.py
   ```

2. **Access the application:**
   - Open your browser to `http://localhost:5000`
   - Create an account or log in
   - Connect your bank account using Plaid Link

## Development Workflow

### Code Formatting
```bash
black . --line-length 88
```

### Linting
```bash
flake8 .
```

### Database Management
The application uses SQLite by default. The database file (`plaid_app.db`) will be created automatically when you first run the app.

### Testing with Plaid Sandbox
- Use Plaid's test credentials in sandbox mode
- Test institution: "user_good" / "pass_good"
- This will create fake accounts and transactions for testing

## Project Structure

```
plaid-googlesheets-budgeting-app/
├── app.py                      # Main Flask application
├── plaid_budget_fetcher.py     # Plaid API service layer
├── database.py                 # Database management
├── requirements.txt            # Python dependencies
├── templates/                  # HTML templates
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── plaid_link.html
│   ├── register.html
│   └── transactions.html
├── .cursorrules               # Cursor IDE configuration
├── .cursorignore              # Files to ignore in Cursor
└── plaid-budgeting.code-workspace  # VS Code workspace
```

## Key Features

- **User Authentication**: Session-based user management
- **Plaid Integration**: Connect multiple bank accounts
- **Account Management**: View account balances and details
- **Transaction Fetching**: Retrieve and display transactions
- **Caching**: Efficient data caching to minimize API calls
- **Multi-Institution Support**: Connect accounts from different banks

## Common Development Tasks

### Adding New Routes
1. Add route handler to `app.py`
2. Use `@login_required` decorator for protected routes
3. Follow the existing error handling pattern
4. Add corresponding HTML template if needed

### Database Operations
1. Add methods to `DatabaseManager` class in `database.py`
2. Use parameterized queries to prevent SQL injection
3. Handle database errors gracefully

### Plaid API Integration
1. Add methods to `PlaidService` class in `plaid_budget_fetcher.py`
2. Implement proper error handling
3. Consider caching for frequently accessed data

## Debugging

### Enable Debug Mode
Set `FLASK_DEBUG=1` in your `.env` file for detailed error messages.

### Common Issues
- **Missing environment variables**: Check your `.env` file
- **Plaid API errors**: Verify your credentials and environment settings
- **Database errors**: Delete `plaid_app.db` to reset the database

## Production Deployment

1. **Environment Variables:**
   - Use production Plaid environment
   - Set strong `SECRET_KEY`
   - Configure proper database URL

2. **Security:**
   - Use HTTPS in production
   - Secure environment variables
   - Implement rate limiting

3. **Performance:**
   - Configure caching (Redis recommended)
   - Use production WSGI server (Gunicorn)
   - Implement logging and monitoring

## Contributing

1. Follow the coding guidelines in `.cursorrules`
2. Test changes thoroughly with Plaid sandbox
3. Ensure proper error handling
4. Update documentation as needed 