from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
import hmac
import hashlib

def sign_data(private_key, data: bytes) -> str:
    """
    Signs bytes data using ECDSA with SHA-256.
    Returns the signature as a hex-encoded string.
    """
    signature = private_key.sign(
        data,
        ec.ECDSA(hashes.SHA256())
    )
    return signature.hex()

def verify_signature(public_key, signature_hex: str, data: bytes) -> bool:
    """
    Verifies a hex-encoded ECDSA signature against the original data.
    Returns True if valid, False if invalid or upon error.
    """
    try:
        signature_bytes = bytes.fromhex(signature_hex)
        public_key.verify(
            signature_bytes,
            data,
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False

def generate_hmac(key: bytes, data: bytes) -> str:
    """
    Generates a SHA-256 HMAC of the data using the provided secret key.
    """
    return hmac.new(key, data, hashlib.SHA256).hexdigest()

def verify_hmac(key: bytes, data: bytes, mac_hex: str) -> bool:
    """
    Verifies that a SHA-256 HMAC matches the computed HMAC.
    """
    try:
        computed = generate_hmac(key, data)
        return hmac.compare_digest(computed, mac_hex)
    except Exception:
        return False
