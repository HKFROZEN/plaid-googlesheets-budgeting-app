# PostgreSQL Setup for Plaid Budgeting App

This directory contains PostgreSQL setup scripts and migration tools to transition from SQLite to PostgreSQL for better scalability.

## Files Overview

- `01_create_schema.sql` - Creates the PostgreSQL database schema
- `02_migration.sql` - Reference for manual data migration (not recommended)
- `03_cleanup.sql` - Development script to reset database
- `README.md` - This file

## Prerequisites

1. **PostgreSQL Server**: Install PostgreSQL (version 12 or higher recommended)
   - Windows: Download from https://www.postgresql.org/download/windows/
   - Mac: `brew install postgresql`
   - Ubuntu: `sudo apt-get install postgresql postgresql-contrib`

2. **Python Dependencies**: Install required packages
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**: Create a `.env` file with your PostgreSQL settings

## Quick Setup

### 1. Environment Configuration

Create a `.env` file in your project root:

```bash
# Generate example .env file
python setup_postgres.py --create-env
```

Then edit the `.env` file with your PostgreSQL credentials:

```env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=plaid_budgeting_app

# SQLite Configuration (for migration)
SQLITE_DB_PATH=plaid_app.db
```

### 2. Initialize New PostgreSQL Database

```bash
# Create database and schema
python setup_postgres.py --init
```

### 3. Migrate from SQLite (Optional)

If you have existing SQLite data:

```bash
# Migrate existing data from SQLite to PostgreSQL
python setup_postgres.py --migrate
```

### 4. Full Setup (Initialize + Migrate)

```bash
# Initialize database and migrate data in one command
python setup_postgres.py --init --migrate
```

## Manual Setup

If you prefer manual setup:

### 1. Create Database

Connect to PostgreSQL and create the database:

```sql
CREATE DATABASE plaid_budgeting_app;
```

### 2. Run Schema Script

```bash
psql -U postgres -d plaid_budgeting_app -f sql/01_create_schema.sql
```

### 3. Migrate Data (if needed)

Use the Python migration script:

```bash
python setup_postgres.py --migrate
```

## Development

### Reset Database

**WARNING**: This will delete all data!

```bash
# Reset database (development only)
python setup_postgres.py --reset
```

### Update Application Code

To use PostgreSQL instead of SQLite:

1. Replace `from database import DatabaseManager` with `from database_postgres import DatabaseManager`
2. Or modify your existing `database.py` to use PostgreSQL
3. Update your application configuration to use PostgreSQL connection parameters

## Database Schema

The PostgreSQL schema includes:

- **users**: User authentication and profile information
- **user_tokens**: Plaid access tokens and institution information
- **accounts**: Cached account information from Plaid
- **transactions**: Cached transaction data from Plaid

### Key Improvements over SQLite

- **SERIAL** primary keys with proper sequences
- **DECIMAL** for precise monetary values
- **TIMESTAMP WITH TIME ZONE** for proper timezone handling
- **Automatic triggers** for updating `updated_at` timestamps
- **Better indexing** for improved query performance
- **Enhanced constraints** and data validation

## Connection Configuration

The database connection uses environment variables:

```python
db_config = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'plaid_budgeting_app'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}
```

## Troubleshooting

### Connection Issues

1. **Check PostgreSQL service**: Ensure PostgreSQL is running
2. **Verify credentials**: Check username/password in `.env`
3. **Check permissions**: Ensure user has database creation privileges
4. **Firewall**: Ensure PostgreSQL port (5432) is accessible

### Migration Issues

1. **SQLite file not found**: Check `SQLITE_DB_PATH` in `.env`
2. **Permission denied**: Ensure PostgreSQL user has write permissions
3. **Constraint violations**: Check for duplicate data in SQLite

### Performance Tips

1. **Indexes**: The schema includes optimized indexes for common queries
2. **Connection pooling**: Consider using connection pooling for production
3. **Query optimization**: Use EXPLAIN ANALYZE to optimize slow queries

## Production Considerations

1. **Backup strategy**: Implement regular database backups
2. **Connection pooling**: Use pgbouncer or similar for connection management
3. **Monitoring**: Set up monitoring for database performance
4. **Security**: Use SSL connections and proper firewall rules
5. **Scaling**: Consider read replicas for high-traffic applications

## Support

For issues with the migration or setup:

1. Check the logs in `postgres_setup.log`
2. Verify PostgreSQL server status
3. Check environment variable configuration
4. Review database permissions and access rights 