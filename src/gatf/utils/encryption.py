"""
GATF Encryption Utilities

This module provides encryption, decryption, and hashing functionality
for securing sensitive data within the GATF framework.
"""

import os
import base64
import hashlib
import secrets
from typing import Union, Tuple, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import bcrypt


class EncryptionError(Exception):
    """Raised when encryption/decryption operations fail"""
    pass


def generate_key(key_size: int = 32) -> bytes:
    """
    Generate a secure random encryption key
    
    Args:
        key_size: Size of the key in bytes (default: 32 for AES-256)
    
    Returns:
        Random key bytes
    """
    return secrets.token_bytes(key_size)


def generate_fernet_key() -> bytes:
    """
    Generate a Fernet encryption key
    
    Returns:
        Fernet key suitable for use with Fernet encryption
    """
    return Fernet.generate_key()


def derive_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = 100000,
    key_size: int = 32
) -> Tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using PBKDF2
    
    Args:
        password: Password to derive key from
        salt: Salt for key derivation (generated if not provided)
        iterations: Number of PBKDF2 iterations
        key_size: Size of the derived key in bytes
    
    Returns:
        Tuple of (derived_key, salt)
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_size,
        salt=salt,
        iterations=iterations,
        backend=default_backend()
    )
    
    key = kdf.derive(password.encode('utf-8'))
    return key, salt


def encrypt_data(
    data: Union[str, bytes],
    key: Optional[bytes] = None,
    algorithm: str = "AES-256-GCM"
) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt data using specified algorithm
    
    Args:
        data: Data to encrypt (string or bytes)
        key: Encryption key (generated if not provided)
        algorithm: Encryption algorithm to use
    
    Returns:
        Tuple of (encrypted_data, key, nonce/iv)
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if key is None:
        key = generate_key()
    
    if algorithm == "AES-256-GCM":
        return _encrypt_aes_gcm(data, key)
    elif algorithm == "Fernet":
        return _encrypt_fernet(data, key)
    else:
        raise EncryptionError(f"Unsupported algorithm: {algorithm}")


def decrypt_data(
    encrypted_data: bytes,
    key: bytes,
    nonce: Optional[bytes] = None,
    algorithm: str = "AES-256-GCM"
) -> bytes:
    """
    Decrypt data using specified algorithm
    
    Args:
        encrypted_data: Encrypted data
        key: Decryption key
        nonce: Nonce/IV used during encryption
        algorithm: Decryption algorithm to use
    
    Returns:
        Decrypted data bytes
    """
    if algorithm == "AES-256-GCM":
        if nonce is None:
            raise EncryptionError("Nonce required for AES-GCM decryption")
        return _decrypt_aes_gcm(encrypted_data, key, nonce)
    elif algorithm == "Fernet":
        return _decrypt_fernet(encrypted_data, key)
    else:
        raise EncryptionError(f"Unsupported algorithm: {algorithm}")


def _encrypt_aes_gcm(data: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """Encrypt using AES-256-GCM"""
    nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
    
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce),
        backend=default_backend()
    )
    
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(data) + encryptor.finalize()
    
    # Combine encrypted data with authentication tag
    encrypted_with_tag = encrypted_data + encryptor.tag
    
    return encrypted_with_tag, key, nonce


def _decrypt_aes_gcm(encrypted_data: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt using AES-256-GCM"""
    # Extract authentication tag (last 16 bytes)
    tag = encrypted_data[-16:]
    ciphertext = encrypted_data[:-16]
    
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce, tag),
        backend=default_backend()
    )
    
    decryptor = cipher.decryptor()
    try:
        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted_data
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {str(e)}")


def _encrypt_fernet(data: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """Encrypt using Fernet symmetric encryption"""
    # Ensure key is properly formatted for Fernet
    if len(key) != 32:
        key = hashlib.sha256(key).digest()
    
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    
    encrypted_data = f.encrypt(data)
    return encrypted_data, key, b""  # Fernet includes nonce in encrypted data


def _decrypt_fernet(encrypted_data: bytes, key: bytes) -> bytes:
    """Decrypt using Fernet symmetric encryption"""
    # Ensure key is properly formatted for Fernet
    if len(key) != 32:
        key = hashlib.sha256(key).digest()
    
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    
    try:
        decrypted_data = f.decrypt(encrypted_data)
        return decrypted_data
    except Exception as e:
        raise EncryptionError(f"Decryption failed: {str(e)}")


def hash_data(
    data: Union[str, bytes],
    algorithm: str = "SHA256",
    salt: Optional[bytes] = None
) -> str:
    """
    Generate a hash of the data
    
    Args:
        data: Data to hash
        algorithm: Hash algorithm to use
        salt: Optional salt to add
    
    Returns:
        Hex string of the hash
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if salt:
        data = salt + data
    
    if algorithm == "SHA256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "SHA512":
        return hashlib.sha512(data).hexdigest()
    elif algorithm == "SHA3-256":
        return hashlib.sha3_256(data).hexdigest()
    elif algorithm == "BLAKE2b":
        return hashlib.blake2b(data).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Password to hash
    
    Returns:
        Hashed password string
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash
    
    Args:
        password: Password to verify
        hashed: Bcrypt hash to verify against
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def generate_api_key(prefix: str = "gatf", length: int = 32) -> str:
    """
    Generate a secure API key
    
    Args:
        prefix: Prefix for the API key
        length: Length of the random portion
    
    Returns:
        API key string
    """
    random_part = secrets.token_urlsafe(length)
    return f"{prefix}_{random_part}"


def mask_sensitive_data(data: str, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    Mask sensitive data for logging/display
    
    Args:
        data: Sensitive data to mask
        visible_chars: Number of characters to keep visible at start and end
        mask_char: Character to use for masking
    
    Returns:
        Masked string
    """
    if len(data) <= visible_chars * 2:
        return mask_char * len(data)
    
    return (
        data[:visible_chars] +
        mask_char * (len(data) - visible_chars * 2) +
        data[-visible_chars:]
    )


class EncryptionManager:
    """Manager class for handling encryption operations with key management"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize encryption manager
        
        Args:
            master_key: Master key for deriving other keys
        """
        self.master_key = master_key or generate_key()
        self._key_cache = {}
    
    def derive_key(self, context: str, key_size: int = 32) -> bytes:
        """
        Derive a context-specific key from master key
        
        Args:
            context: Context identifier for the key
            key_size: Size of derived key
        
        Returns:
            Derived key bytes
        """
        if context in self._key_cache:
            return self._key_cache[context]
        
        # Use HKDF-like derivation
        info = f"GATF-{context}".encode('utf-8')
        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            self.master_key,
            info,
            iterations=1,
            dklen=key_size
        )
        
        self._key_cache[context] = derived_key
        return derived_key
    
    def encrypt_field(self, field_name: str, value: Union[str, bytes]) -> Tuple[bytes, bytes]:
        """
        Encrypt a specific field using field-specific key
        
        Args:
            field_name: Name of the field (used for key derivation)
            value: Value to encrypt
        
        Returns:
            Tuple of (encrypted_value, nonce)
        """
        key = self.derive_key(f"field-{field_name}")
        encrypted, _, nonce = encrypt_data(value, key)
        return encrypted, nonce
    
    def decrypt_field(self, field_name: str, encrypted: bytes, nonce: bytes) -> bytes:
        """
        Decrypt a specific field
        
        Args:
            field_name: Name of the field (used for key derivation)
            encrypted: Encrypted value
            nonce: Nonce used during encryption
        
        Returns:
            Decrypted value
        """
        key = self.derive_key(f"field-{field_name}")
        return decrypt_data(encrypted, key, nonce)
    
    def rotate_master_key(self, new_master_key: bytes) -> Dict[str, bytes]:
        """
        Rotate master key and return new derived keys
        
        Args:
            new_master_key: New master key
        
        Returns:
            Dictionary of context -> new derived key mappings
        """
        old_keys = dict(self._key_cache)
        self.master_key = new_master_key
        self._key_cache.clear()
        
        # Re-derive all cached keys with new master
        new_keys = {}
        for context in old_keys:
            new_keys[context] = self.derive_key(context)
        
        return new_keys