#!/usr/bin/env python3
"""
Plaid Budget Information Fetcher

This script connects to the Plaid API to retrieve budget-related information
including account balances, transactions, and categorized spending data.
"""

import os
import json
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv
import plaid
from plaid.api import plaid_api
from plaid.model.products import Products
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.country_code import CountryCode
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.transactions_get_request import TransactionsGetRequest

from flask import Flask, request, jsonify
import pandas as pd
from database import DatabaseManager


@dataclass
class BudgetData:
    """Data class to hold budget information"""
    accounts: List[Dict]
    transactions: List[Dict]
    balances: Dict[str, float]
    spending_by_category: Dict[str, float]
    total_spent: float
    total_income: float


class PlaidService:
    """Service class to manage Plaid authentication and operations"""
    
    def __init__(self, client_id: str, secret: str, environment: str = 'sandbox'):
        """
        Initialize the Plaid service
        
        Args:
            client_id: Plaid client ID
            secret: Plaid secret key
            environment: Plaid environment (sandbox, development, production)
        """
        self.client_id = client_id
        self.secret = secret
        self.environment = environment
        self.db = DatabaseManager()
        
        # Configure Plaid client
        if self.environment == 'sandbox':
            host = plaid.Environment.Sandbox
        elif self.environment == 'production':
            host = plaid.Environment.Production
        else:
            raise ValueError(f"Invalid environment: {self.environment}")
        self.configuration = plaid.Configuration(
            host=host,
            api_key={
                'clientId': self.client_id,
                'secret': self.secret,
                'plaidVersion': '2020-09-14'
            }
        )
        
        api_client = plaid.ApiClient(self.configuration)
        self.client = plaid_api.PlaidApi(api_client)
    
    def exchange_public_token(self, public_token: str, user_id: int) -> Dict:
        """
        Exchange public token for access token and store in database
        
        Args:
            public_token: The public token to exchange
            user_id: The user ID to associate the token with
            
        Returns:
            Dictionary containing access token and item ID
        """
        try:
            exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
            exchange_response = self.client.item_public_token_exchange(exchange_request)
            
            # Extract tokens from response
            access_token = exchange_response['access_token']
            item_id = exchange_response['item_id']
            
            # Get institution information
            institution_id = None
            institution_name = None
            
            try:
                # Get item details to find institution ID
                item_request = ItemGetRequest(access_token=access_token)
                item_response = self.client.item_get(item_request)
                institution_id = item_response['item']['institution_id']
                
                # Get institution details
                if institution_id:
                    inst_request = InstitutionsGetByIdRequest(
                        institution_id=institution_id,
                        country_codes=[CountryCode('US')]
                    )
                    inst_response = self.client.institutions_get_by_id(inst_request)
                    institution_name = inst_response['institution']['name']
                    
            except Exception as e:
                print(f"Warning: Could not fetch institution information: {e}")
                # Continue without institution info
            
            # Store token in database
            success = self.db.store_user_token(
                user_id=user_id,
                access_token=access_token,
                item_id=item_id,
                public_token=public_token,
                institution_id=institution_id,
                institution_name=institution_name
            )
            
            if not success:
                raise Exception("Failed to store access token in database")
            
            # Get the token ID for storing accounts
            token_data = self.db.get_user_tokens(user_id)
            token_id = None
            for token in token_data:
                if token['item_id'] == item_id:
                    token_id = token['id']
                    break
            
            if token_id:
                # Fetch and store initial account data
                try:
                    request = AccountsGetRequest(access_token=access_token)
                    response = self.client.accounts_get(request)
                    accounts = response.to_dict()['accounts']
                    
                    # Add institution info and classification to accounts
                    for account in accounts:
                        account['institution_name'] = institution_name
                        account['account_classification'] = self._classify_account(account)
                        
                        # Format balance for display
                        if 'balances' in account and 'current' in account['balances']:
                            current_balance = account['balances']['current']
                            if current_balance is not None:
                                account['formatted_balance'] = f"${current_balance:,.2f}"
                            else:
                                account['formatted_balance'] = "N/A"
                        else:
                            account['formatted_balance'] = "N/A"
                    
                    # Store accounts in database
                    self.db.store_accounts(user_id, token_id, accounts)
                    
                except Exception as e:
                    print(f"Warning: Could not fetch initial account data: {e}")
                    # Continue without storing accounts - they'll be fetched later
            
            return exchange_response.to_dict()
        except plaid.ApiException as e:
            raise Exception(f"Token exchange failed: {e.body}")
    
    def _classify_account(self, account: Dict[str, Any]) -> str:
        """
        Classify an account as asset or liability based on its type and subtype
        
        Args:
            account: Account data from Plaid API
            
        Returns:
            'asset' or 'liability'
        """
        account_type = account.get('type', '').lower()
        account_subtype = account.get('subtype', '').lower()
        
        # Classification logic
        if account_type in ['depository', 'investment', 'other']:
            return 'asset'
        elif account_type in ['credit', 'loan']:
            return 'liability'
        else:
            # Default classification based on subtype
            if account_subtype in ['checking', 'savings', 'money market', 'cd', 'brokerage', 'ira', '401k']:
                return 'asset'
            elif account_subtype in ['credit card', 'line of credit', 'mortgage', 'auto', 'student']:
                return 'liability'
            else:
                return 'asset'  # Default to asset
    
    def _fetch_transactions_for_token(self, access_token: str, accounts: List[Dict], 
                                     start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
        """
        Fetch transactions for a specific access token and accounts
        
        Args:
            access_token: Plaid access token
            accounts: List of accounts to fetch transactions for
            start_date: Start date for transaction fetch
            end_date: End date for transaction fetch
            
        Returns:
            List of transactions filtered to relevant accounts
        """
        transactions_request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date
        )
        
        transactions_response = self.client.transactions_get(transactions_request)
        transactions = transactions_response.to_dict()['transactions']
        
        # Filter transactions to only include those from relevant accounts
        relevant_account_ids = {acc['account_id'] for acc in accounts}
        filtered_transactions = [
            t for t in transactions 
            if t.get('account_id') in relevant_account_ids
        ]
        
        return filtered_transactions
    
    def _format_transactions(self, transactions: List[Dict], institution_name: str) -> List[Dict]:
        """
        Format transactions with institution info and display formatting
        
        Args:
            transactions: List of raw transactions from Plaid API
            institution_name: Name of the institution
            
        Returns:
            List of formatted transactions
        """
        formatted_transactions = []
        for transaction in transactions:
            transaction['institution_name'] = institution_name
            transaction['formatted_amount'] = f"${abs(transaction['amount']):,.2f}"
            transaction['transaction_type'] = 'debit' if transaction['amount'] > 0 else 'credit'
            
            # Extract personal finance category information
            personal_finance_category = transaction.get('personal_finance_category', {})
            if personal_finance_category:
                transaction['category_primary'] = personal_finance_category.get('primary', 'OTHER')
                transaction['category_detailed'] = personal_finance_category.get('detailed', 'OTHER')
                transaction['category_confidence'] = personal_finance_category.get('confidence_level', 'UNKNOWN')
            else:
                # Fallback values if personal_finance_category is not available
                transaction['category_primary'] = 'OTHER'
                transaction['category_detailed'] = 'OTHER'
                transaction['category_confidence'] = 'UNKNOWN'
            
            formatted_transactions.append(transaction)
        
        return formatted_transactions
    
    def get_cached_accounts(self, user_id: int) -> Dict:
        """
        Get cached account information from database
        
        Args:
            user_id: The user ID
            
        Returns:
            Dictionary containing cached account information
        """
        try:
            # Get cached accounts from database
            cached_accounts = self.db.get_cached_accounts(user_id)
            
            # Group accounts by institution
            institutions = {}
            for account in cached_accounts:
                institution_name = account['institution_name']
                if institution_name not in institutions:
                    institutions[institution_name] = {
                        'name': institution_name,
                        'token_id': account['token_id'],
                        'accounts': []
                    }
                institutions[institution_name]['accounts'].append(account)
            
            # Format institutions list
            institutions_list = []
            for inst_name, inst_data in institutions.items():
                institutions_list.append({
                    'name': inst_name,
                    'token_id': inst_data['token_id'],
                    'account_count': len(inst_data['accounts'])
                })
            
            return {
                'accounts': cached_accounts,
                'institutions': institutions_list,
                'total_accounts': len(cached_accounts),
                'connected_institutions': len(institutions_list),
                'errors': [],
                'is_cached': True
            }
            
        except Exception as e:
            raise Exception(f"Failed to get cached accounts: {str(e)}")
    
    def get_accounts(self, user_id: int, force_refresh: bool = False) -> Dict:
        """
        Get user accounts from all connected institutions
        
        Args:
            user_id: The user ID
            force_refresh: If True, fetch fresh data from Plaid API
            
        Returns:
            Dictionary containing aggregated account information from all institutions
        """
        # If not forcing refresh, try to get cached data first
        if not force_refresh:
            try:
                cached_result = self.get_cached_accounts(user_id)
                if cached_result['accounts']:
                    return cached_result
            except Exception:
                # If cached data fails, fall back to API
                pass
        
        # Get all user's access tokens from database
        tokens_data = self.db.get_user_tokens(user_id)
        if not tokens_data:
            raise Exception("No access tokens found for user. Please exchange public token first.")
        
        all_accounts = []
        institutions = []
        errors = []
        
        for token_data in tokens_data:
            access_token = token_data['access_token']
            institution_name = token_data.get('institution_name', 'Unknown Institution')
            token_id = token_data['id']
            
            try:
                request = AccountsGetRequest(access_token=access_token)
                response = self.client.accounts_get(request)
                accounts = response.to_dict()['accounts']
                
                # Add institution info to each account and merge custom names
                for account in accounts:
                    account['institution_name'] = institution_name
                    account['token_id'] = token_id
                    account['account_classification'] = self._classify_account(account)
                    
                    # Format balance for display
                    if 'balances' in account and 'current' in account['balances']:
                        current_balance = account['balances']['current']
                        if current_balance is not None:
                            account['formatted_balance'] = f"${current_balance:,.2f}"
                        else:
                            account['formatted_balance'] = "N/A"
                    else:
                        account['formatted_balance'] = "N/A"
                
                # Get cached accounts to preserve custom names
                cached_accounts = self.db.get_cached_accounts(user_id)
                custom_names = {acc['account_id']: acc['custom_name'] for acc in cached_accounts if acc['custom_name']}
                
                # Merge custom names with fresh account data
                for account in accounts:
                    account_id = account['account_id']
                    if account_id in custom_names:
                        account['custom_name'] = custom_names[account_id]
                        account['display_name'] = custom_names[account_id]
                    else:
                        account['custom_name'] = None
                        account['display_name'] = account['name']
                
                all_accounts.extend(accounts)
                institutions.append({
                    'name': institution_name,
                    'id': token_data.get('institution_id'),
                    'item_id': token_data.get('item_id'),
                    'token_id': token_id,
                    'account_count': len(accounts)
                })
                
                # Store/update accounts in database
                self.db.store_accounts(user_id, token_id, accounts)
                
                # If forcing refresh, also refresh transaction data for this institution
                if force_refresh:
                    try:
                        # Calculate date range for transactions (last 30 days)
                        end_date = datetime.datetime.now().date()
                        start_date = end_date - datetime.timedelta(days=30)
                        
                        # Fetch transactions using helper function
                        filtered_transactions = self._fetch_transactions_for_token(
                            access_token, accounts, start_date, end_date
                        )
                        
                        # Format transactions using helper function
                        formatted_transactions = self._format_transactions(filtered_transactions, institution_name)
                        
                        # Store transactions in database
                        self.db.store_transactions(user_id, formatted_transactions)
                        
                    except plaid.ApiException as trans_e:
                        error_msg = f"Failed to refresh transactions from {institution_name}: {trans_e.body}"
                        errors.append(error_msg)
                        # Continue with accounts even if transaction refresh fails
                
            except plaid.ApiException as e:
                error_msg = f"Failed to get accounts from {institution_name}: {e.body}"
                errors.append(error_msg)
                continue
        
        # No need to format balances again since it's done above
        
        return {
            'accounts': all_accounts,
            'institutions': institutions,
            'total_accounts': len(all_accounts),
            'connected_institutions': len(institutions),
            'errors': errors,
            'is_cached': False
        }
    
    def get_cached_transactions(self, user_id: int, account_types: Optional[list[str]] = None, 
                              account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, limit: int = 100, offset: int = 0) -> Dict:
        """
        Get cached transaction information from database
        
        Args:
            user_id: The user ID
            account_types: Optional list of account types to filter by (e.g., ['depository', 'credit'])
            account_id: Optional specific account ID to filter by
            year: Year to filter by (default: current year)
            month: Optional month to filter by (1-12)
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            
        Returns:
            Dictionary containing cached transaction information
        """
        try:
            # Default to current year if not specified
            if year is None:
                year = datetime.datetime.now().year
            
            # Get cached transactions from database
            cached_transactions = self.db.get_cached_transactions(user_id, account_types, account_id, year, month, limit, offset)
            
            # Get transaction summary
            transaction_summary = self.db.get_transaction_summary(user_id, account_types, account_id, year, month)
            
            return {
                'transactions': cached_transactions,
                'summary': transaction_summary,
                'total_transactions': len(cached_transactions),
                'is_cached': True,
                'account_types_filter': account_types
            }
            
        except Exception as e:
            raise Exception(f"Failed to get cached transactions: {str(e)}")
    
    def get_transactions(self, user_id: int, account_types: Optional[list[str]] = None,
                        account_id: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, force_refresh: bool = False) -> Dict:
        """
        Get user transactions from specified account types
        
        Args:
            user_id: The user ID
            account_types: List of account types to get transactions for (e.g., ['depository', 'credit'])
            year: Year to fetch transactions for (default: current year)
            month: Optional month to filter by (1-12)
            force_refresh: If True, fetch fresh data from Plaid API
            
        Returns:
            Dictionary containing transaction information
        """
        # Default to current year if not specified
        if year is None:
            year = datetime.datetime.now().year
        
        # If not forcing refresh, try to get cached data first
        if not force_refresh:
            try:
                cached_result = self.get_cached_transactions(user_id, account_types, account_id, year, month)
                if cached_result['transactions']:
                    return cached_result
            except Exception:
                # If cached data fails, fall back to API
                pass
        
        # Get all user's access tokens from database
        tokens_data = self.db.get_user_tokens(user_id)
        if not tokens_data:
            raise Exception("No access tokens found for user. Please connect a bank account first.")
        
        all_transactions = []
        errors = []
        
        # Calculate date range based on year and month
        if month:
            # Specific month
            start_date = datetime.date(year, month, 1)
            if month == 12:
                end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        else:
            # Entire year
            start_date = datetime.date(year, 1, 1)
            end_date = datetime.date(year, 12, 31)
        
        for token_data in tokens_data:
            access_token = token_data['access_token']
            institution_name = token_data.get('institution_name', 'Unknown Institution')
            
            try:
                # Get accounts for this token first
                accounts_request = AccountsGetRequest(access_token=access_token)
                accounts_response = self.client.accounts_get(accounts_request)
                accounts = accounts_response.to_dict()['accounts']
                
                # Filter accounts by type if specified
                if account_types:
                    accounts = [acc for acc in accounts if acc.get('type') in account_types]
                
                if not accounts:
                    continue
                
                # Fetch transactions using helper function
                filtered_transactions = self._fetch_transactions_for_token(
                    access_token, accounts, start_date, end_date
                )
                
                # Format transactions using helper function
                formatted_transactions = self._format_transactions(filtered_transactions, institution_name)
                
                all_transactions.extend(formatted_transactions)
                
                # Store transactions in database
                self.db.store_transactions(user_id, formatted_transactions)
                
            except plaid.ApiException as e:
                error_msg = f"Failed to get transactions from {institution_name}: {e.body}"
                errors.append(error_msg)
                continue
        
        # Sort transactions by date (newest first)
        all_transactions.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Get transaction summary
        transaction_summary = self.db.get_transaction_summary(user_id, account_types, None, year, month)
        
        return {
            'transactions': all_transactions,
            'summary': transaction_summary,
            'total_transactions': len(all_transactions),
            'errors': errors,
            'is_cached': False,
            'account_types_filter': account_types,
            'period_year': year,
            'period_month': month
        }
    
    def has_access_token(self, user_id: int) -> bool:
        """Check if user has any valid access tokens"""
        tokens_data = self.db.get_user_tokens(user_id)
        return len(tokens_data) > 0
    
    def get_institutions_count(self, user_id: int) -> int:
        """Get the count of connected institutions for a user"""
        tokens_data = self.db.get_user_tokens(user_id)
        return len(tokens_data)
    
    def revoke_access_token(self, user_id: int, token_id: Optional[int] = None) -> bool:
        """
        Revoke access token(s) for a user
        
        Args:
            user_id: The user ID
            token_id: Optional specific token ID to revoke, if None revokes all
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if token_id:
                # Revoke specific token
                tokens_data = self.db.get_user_tokens(user_id)
                token_to_revoke = next((t for t in tokens_data if t['id'] == token_id), None)
                
                if not token_to_revoke:
                    return False
                
                # Delete associated accounts first
                self.db.delete_accounts_by_token(user_id, token_id)
                
                # Call Plaid API to revoke the token
                # Note: This is a simplified example - you might want to implement ItemRemove
                success = self.db.delete_user_token(user_id, token_id)
                return success
            else:
                # Revoke all tokens
                tokens_data = self.db.get_user_tokens(user_id)
                
                # Delete all associated accounts first
                for token_data in tokens_data:
                    self.db.delete_accounts_by_token(user_id, token_data['id'])
                
                # Call Plaid API to revoke each token
                # Note: This is a simplified example
                success = self.db.delete_user_token(user_id)
                return success
                
        except Exception:
            return False
    
    def create_link_token(self, user_id: int) -> Dict:
        """
        Create a link token for Plaid Link initialization
        
        Args:
            user_id: The user ID for link token creation
            
        Returns:
            Dictionary containing link token
        """
        try:
            request = LinkTokenCreateRequest(
                products=self.get_products(),
                client_name="Plaid Flask App",
                country_codes=[CountryCode('US')],
                language='en',
                user=LinkTokenCreateRequestUser(client_user_id=str(user_id))
            )
            
            response = self.client.link_token_create(request)
            return response.to_dict()
        except plaid.ApiException as e:
            raise Exception(f"Link token creation failed: {e.body}")
    
    def get_products(self) -> List:
        """Get list of Plaid products"""
        return [Products('transactions')]


