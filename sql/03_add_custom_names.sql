-- PostgreSQL Migration: Add custom_name column to accounts table
-- This allows users to set custom names for their accounts (e.g., "John's Checking", "Jane's Savings")

-- Add custom_name column to accounts table
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS custom_name VARCHAR(255);

-- Create index for custom_name searches
CREATE INDEX IF NOT EXISTS idx_accounts_custom_name ON accounts(custom_name);

-- Add a comment to the column
COMMENT ON COLUMN accounts.custom_name IS 'User-defined custom name for the account (e.g., for couples to identify whose account it is)';

-- Optional: Add a constraint to prevent empty strings (but allow NULL)
ALTER TABLE accounts ADD CONSTRAINT check_custom_name_not_empty 
    CHECK (custom_name IS NULL OR length(trim(custom_name)) > 0); 