-- Migration Script: SQLite to PostgreSQL
-- This script provides guidance and examples for migrating data from SQLite to PostgreSQL

-- IMPORTANT: This script is meant to be used as a reference.
-- The actual migration should be done using the Python migration script (migrate_to_postgres.py)
-- that handles the data conversion and transfer automatically.

-- If you need to manually migrate data, you can export from SQLite and import to PostgreSQL:

-- 1. Export from SQLite (run this in your SQLite database):
-- .mode csv
-- .output users.csv
-- SELECT * FROM users;
-- .output user_tokens.csv
-- SELECT * FROM user_tokens;
-- .output accounts.csv
-- SELECT * FROM accounts;
-- .output transactions.csv
-- SELECT * FROM transactions;

-- 2. Import to PostgreSQL (run these commands in PostgreSQL):
-- Note: You may need to adjust the COPY commands based on your CSV format

-- Example import commands (adjust paths as needed):
-- COPY users(id, username, password_hash, salt, created_at) FROM '/path/to/users.csv' CSV HEADER;
-- COPY user_tokens(id, user_id, access_token, item_id, public_token, institution_id, institution_name, created_at, updated_at) FROM '/path/to/user_tokens.csv' CSV HEADER;
-- COPY accounts(id, user_id, token_id, account_id, name, type, subtype, institution_name, current_balance, available_balance, iso_currency_code, unofficial_currency_code, account_classification, is_active, created_at, updated_at) FROM '/path/to/accounts.csv' CSV HEADER;
-- COPY transactions(id, user_id, account_id, transaction_id, amount, iso_currency_code, unofficial_currency_code, date, datetime, authorized_date, authorized_datetime, name, merchant_name, account_owner, category, subcategory, transaction_type, pending, institution_name, created_at, updated_at) FROM '/path/to/transactions.csv' CSV HEADER;

-- 3. Update sequences after manual import (only needed if you manually imported data):
-- SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
-- SELECT setval('user_tokens_id_seq', (SELECT MAX(id) FROM user_tokens));
-- SELECT setval('accounts_id_seq', (SELECT MAX(id) FROM accounts));
-- SELECT setval('transactions_id_seq', (SELECT MAX(id) FROM transactions));

-- 4. Data type conversions that might be needed:
-- SQLite INTEGER (for primary keys) → PostgreSQL SERIAL
-- SQLite TEXT → PostgreSQL VARCHAR or TEXT
-- SQLite REAL → PostgreSQL DECIMAL
-- SQLite TIMESTAMP → PostgreSQL TIMESTAMP WITH TIME ZONE
-- SQLite BOOLEAN → PostgreSQL BOOLEAN (should work directly)

-- 5. Verify migration:
-- SELECT COUNT(*) FROM users;
-- SELECT COUNT(*) FROM user_tokens;
-- SELECT COUNT(*) FROM accounts;
-- SELECT COUNT(*) FROM transactions;

-- 6. Test constraints and relationships:
-- INSERT INTO users (username, password_hash, salt) VALUES ('test_user', 'hash', 'salt');
-- DELETE FROM users WHERE username = 'test_user';

-- RECOMMENDED: Use the Python migration script instead of manual migration
-- The Python script handles all these conversions automatically and safely. 