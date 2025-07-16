# Plaid Budget Fetcher

A Python script that connects to the Plaid API to retrieve comprehensive budget information including account balances, transactions, and categorized spending data.

## Features

- Fetch all account balances from connected financial institutions
- Retrieve recent transactions with categorization
- Calculate total income and expenses
- Categorize spending by transaction type
- Export data to CSV and JSON formats
- Display formatted budget summary

## Prerequisites

1. **Plaid Account**: Sign up at [Plaid Dashboard](https://dashboard.plaid.com/)
2. **API Credentials**: Get your Client ID, Secret, and Access Token from Plaid
3. **Python 3.7+**

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Set up your environment variables. You can either:

### Option 1: Create a .env file
Create a `.env` file in the project root:
```
PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_secret_key_here
PLAID_ACCESS_TOKEN=your_access_token_here
PLAID_ENVIRONMENT=sandbox
```

### Option 2: Set environment variables directly
```bash
export PLAID_CLIENT_ID=your_client_id_here
export PLAID_SECRET=your_secret_key_here
export PLAID_ACCESS_TOKEN=your_access_token_here
export PLAID_ENVIRONMENT=sandbox
```

## Usage

Run the script:
```bash
python plaid_budget_fetcher.py
```

The script will:
1. Connect to Plaid API using your credentials
2. Fetch account information and recent transactions (last 30 days)
3. Display a formatted budget summary
4. Export transaction data to `budget_data.csv`
5. Save complete budget data to `budget_data.json`

## Output

### Console Output
- **Budget Summary**: Total income, expenses, and net amount
- **Account Balances**: Current balance for each connected account
- **Spending by Category**: Breakdown of expenses by category
- **Recent Transactions**: List of the most recent transactions

### File Output
- `budget_data.csv`: Transaction data in CSV format
- `budget_data.json`: Complete budget data in JSON format

## Environment Settings

- **sandbox**: Use Plaid's sandbox environment for testing
- **development**: Use for development with live data
- **production**: Use for production applications

## Getting Your Access Token

To get an access token, you'll need to:

1. Use Plaid's Link flow to connect a bank account
2. Exchange the public token for an access token
3. Use that access token in your environment variables

For testing purposes, you can use Plaid's sandbox environment with test credentials.

## Example Output

```
Fetching budget data from 2024-01-01 to 2024-01-31

=== BUDGET SUMMARY ===
Total Income: $5,000.00
Total Spent: $3,200.00
Net: $1,800.00

=== ACCOUNT BALANCES ===
Checking Account: $2,500.00
Savings Account: $10,000.00

=== SPENDING BY CATEGORY ===
Food and Drink: $800.00
Transportation: $400.00
Shopping: $350.00
...

=== RECENT TRANSACTIONS (45 total) ===
2024-01-30: Grocery Store - $85.42
2024-01-29: Gas Station - $45.00
...
```

## Troubleshooting

1. **Import Errors**: Make sure all dependencies are installed with `pip install -r requirements.txt`
2. **API Errors**: Check that your Plaid credentials are correct and your access token is valid
3. **No Data**: Ensure your access token has permission to access accounts and transactions

## Security Notes

- Never commit your `.env` file to version control
- Keep your Plaid credentials secure
- Use environment-specific credentials (sandbox for testing, production for live data)

## License

This project is provided as-is for educational and personal use. 