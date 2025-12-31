"""Kalshi authentication and request signing."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAuth:
    """Handles Kalshi API authentication and request signing."""
    
    def __init__(self, api_key: str, private_key_pem: str):
        """Initialize with API credentials.
        
        Args:
            api_key: Kalshi API key
            private_key_pem: Private key in PEM format
        """
        self.api_key = api_key
        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
        )
    
    def sign_request(self, method: str, path: str) -> dict[str, str]:
        """Sign a request and return headers.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            
        Returns:
            Dictionary of headers to include
        """
        timestamp = str(int(time.time() * 1000))
        
        # Create message to sign: timestamp + method + path
        message = timestamp + method + path
        message_bytes = message.encode('utf-8')
        
        # Sign with RSA PSS
        signature = self.private_key.sign(
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Base64 encode signature
        import base64
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return {
            'KALSHI-ACCESS-KEY': self.api_key,
            'KALSHI-ACCESS-TIMESTAMP': timestamp,
            'KALSHI-ACCESS-SIGNATURE': signature_b64,
            'Content-Type': 'application/json',
        }