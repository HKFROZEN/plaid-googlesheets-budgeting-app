-- Cleanup Script for PostgreSQL
-- This script drops all tables and recreates them - USE WITH CAUTION!
-- This is primarily for development environments

-- WARNING: This will DELETE ALL DATA in the database!
-- Only use this in development environments or when you want to completely reset the database

-- Drop tables in correct order (respecting foreign key constraints)
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS user_tokens CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Drop extensions (optional, comment out if you want to keep them)
-- DROP EXTENSION IF EXISTS "uuid-ossp";

-- Recreate the schema by running the create schema script
-- You can run this script followed by 01_create_schema.sql to reset everything

-- Alternative: Instead of dropping, you can truncate all tables to keep structure:
-- TRUNCATE TABLE transactions, accounts, user_tokens, users RESTART IDENTITY CASCADE;

-- Or delete all data without resetting sequences:
-- DELETE FROM transactions;
-- DELETE FROM accounts;
-- DELETE FROM user_tokens;
-- DELETE FROM users; 