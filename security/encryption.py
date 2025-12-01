"""Encryption and decryption with user key"""
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from config.settings import settings


def derive_user_key(user_id: int) -> bytes:
    """Generate unique key for each user"""
    # Combine master key with user_id
    combined = f"{settings.MASTER_ENCRYPTION_KEY}_{user_id}".encode()
    
    # Use SHA-256 to generate 32-byte key
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(combined)
    return digest.finalize()


def encrypt_password(user_id: int, password: str) -> str:
    """Encrypt password with user key"""
    if not password:
        return ""
    
    user_key = derive_user_key(user_id)
    
    # Create AESGCM instance
    aesgcm = AESGCM(user_key)
    
    # Generate nonce (12 bytes for GCM)
    import os
    nonce = os.urandom(12)
    
    # Encrypt
    password_bytes = password.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, password_bytes, None)
    
    # Combine nonce and ciphertext and encode to base64
    encrypted_data = nonce + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_password(user_id: int, encrypted_password: str) -> str:
    """Decrypt password with user key"""
    if not encrypted_password:
        return ""
    
    try:
        user_key = derive_user_key(user_id)
        
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_password.encode('utf-8'))
        
        # Separate nonce (first 12 bytes) and ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Decrypt
        aesgcm = AESGCM(user_key)
        password_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        
        return password_bytes.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Decryption error: {str(e)}")
