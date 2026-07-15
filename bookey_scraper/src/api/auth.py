"""
SmartFM Authentication Module
Handles authentication with the SmartFM API and token management
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict
import requests
from datetime import datetime, timedelta

class SmartFMAuth:
    def __init__(self, base_url: str = "http://localhost:6969"):
        """
        Initialize the SmartFM authentication handler
        
        Args:
            base_url (str): Base URL for the SmartFM API
        """
        self.base_url = base_url
        self.login_url = f"{base_url}/auth/studio/signin"
        self.token_file = Path("data/auth/tokens.json")
        self.tokens = self._load_tokens()
        
    def _load_tokens(self) -> Dict:
        """Load tokens from file if they exist"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_tokens(self, tokens: Dict):
        """Save tokens to file"""
        # Create directory if it doesn't exist
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.token_file, 'w') as f:
            json.dump(tokens, f, indent=2)
    
    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid"""
        if not self.tokens:
            return False
            
        # Check if token exists and hasn't expired
        if 'access_token' not in self.tokens or 'expires_at' not in self.tokens:
            return False
            
        expires_at = datetime.fromisoformat(self.tokens['expires_at'])
        return datetime.now() < expires_at
    
    def login(self, email: str, password: str) -> Optional[str]:
        """
        Login to the SmartFM API and get an access token
        
        Args:
            email (str): User's email
            password (str): User's password
            
        Returns:
            Optional[str]: Access token if login successful, None otherwise
        """
        # Check if we have a valid token already
        if self._is_token_valid():
            return self.tokens['access_token']
        
        # Create login request body
        login_body = {
            "email": email,
            "password": password
        }

        print(f"Sending login request to {self.login_url} with payload: {json.dumps(login_body)}")
        
        try:
            # Send login request
            response = requests.post(
                self.login_url,
                json=login_body,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            if not data.get('success'):
                print(f"Login failed: {data.get('message', 'Unknown error')}")
                return None
                
            # Extract tokens
            tokens = {
                'access_token': data['data']['accessToken'],
                'refresh_token': data['data']['refreshToken'],
                'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()  # Assuming 1 hour expiry
            }
            
            # Save tokens
            self.tokens = tokens
            self._save_tokens(tokens)
            
            return tokens['access_token']
            
        except requests.exceptions.RequestException as e:
            print(f"Login request failed: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Error parsing login response: {e}")
            return None
    
    def get_valid_token(self, email: str, password: str) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary
        
        Args:
            email (str): User's email
            password (str): User's password
            
        Returns:
            Optional[str]: Valid access token if successful, None otherwise
        """
        if self._is_token_valid():
            return self.tokens['access_token']
            
        return self.login(email, password)
    
    def logout(self):
        """Clear stored tokens"""
        self.tokens = {}
        if self.token_file.exists():
            self.token_file.unlink() 