#!/usr/bin/env python3
"""
Setup script for Plaid Budget Fetcher
"""

import os
import subprocess
import sys

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        return False

def create_env_file():
    """Create .env file if it doesn't exist"""
    if os.path.exists('.env'):
        print("✓ .env file already exists")
        return True
    
    print("Creating .env file...")
    env_content = """# Plaid API Configuration
# Get these values from your Plaid Dashboard: https://dashboard.plaid.com/

PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_secret_key_here
PLAID_ACCESS_TOKEN=your_access_token_here
PLAID_ENVIRONMENT=sandbox  # sandbox, development, or production
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✓ .env file created successfully")
        print("⚠️  Please edit .env file with your actual Plaid credentials")
        return True
    except Exception as e:
        print(f"✗ Failed to create .env file: {e}")
        return False

def main():
    """Main setup function"""
    print("=== Plaid Budget Fetcher Setup ===\n")
    
    # Install requirements
    if not install_requirements():
        print("Setup failed. Please install requirements manually.")
        return False
    
    # Create .env file
    if not create_env_file():
        print("Setup completed with warnings. Please create .env file manually.")
        return False
    
    print("\n=== Setup Complete ===")
    print("Next steps:")
    print("1. Edit .env file with your Plaid credentials")
    print("2. Run: python plaid_budget_fetcher.py")
    print("\nFor help getting Plaid credentials, see README.md")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 