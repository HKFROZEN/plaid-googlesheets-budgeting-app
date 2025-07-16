-- PostgreSQL Schema Setup for Plaid Budgeting App
-- This script creates the database schema equivalent to the SQLite implementation

-- Create database extension for UUID generation (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create user_tokens table
CREATE TABLE IF NOT EXISTS user_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    item_id VARCHAR(255),
    public_token TEXT,
    institution_id VARCHAR(255),
    institution_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Create accounts table for caching account information
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_id INTEGER NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    subtype VARCHAR(100),
    institution_name VARCHAR(255),
    current_balance DECIMAL(15,2),
    available_balance DECIMAL(15,2),
    iso_currency_code VARCHAR(3) DEFAULT 'USD',
    unofficial_currency_code VARCHAR(10),
    account_classification VARCHAR(20) NOT NULL CHECK (account_classification IN ('asset', 'liability')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (token_id) REFERENCES user_tokens (id) ON DELETE CASCADE,
    UNIQUE(user_id, account_id)
);

-- Create transactions table for caching transaction data
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    account_id VARCHAR(255) NOT NULL,
    transaction_id VARCHAR(255) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    iso_currency_code VARCHAR(3) DEFAULT 'USD',
    unofficial_currency_code VARCHAR(10),
    date DATE NOT NULL,
    datetime TIMESTAMP WITH TIME ZONE,
    authorized_date DATE,
    authorized_datetime TIMESTAMP WITH TIME ZONE,
    name VARCHAR(500) NOT NULL,
    merchant_name VARCHAR(255),
    account_owner VARCHAR(255),
    category VARCHAR(255),
    subcategory VARCHAR(255),
    transaction_type VARCHAR(50),
    pending BOOLEAN DEFAULT FALSE,
    institution_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(user_id, transaction_id)
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_tokens_user_id ON user_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_token_id ON accounts(token_id);
CREATE INDEX IF NOT EXISTS idx_accounts_account_id ON accounts(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_transaction_id ON transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);

-- Create composite indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_accounts_user_token ON accounts(user_id, token_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_account ON transactions(user_id, account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date_category ON transactions(date, category);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at columns
CREATE TRIGGER update_user_tokens_updated_at BEFORE UPDATE ON user_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your environment)
-- These are example permissions, adjust for your specific user/role setup
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO plaid_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO plaid_app_user; 