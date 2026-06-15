from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def generate_key_pair():
    """
    Generates a new ECDSA private/public key pair using the SECP256R1 (NIST P-256) curve.
    """
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    return private_key, public_key

def serialize_private_key(private_key) -> str:
    """
    Serializes a private key object to an unencrypted PEM format string.
    """
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    return pem.decode('utf-8')

def serialize_public_key(public_key) -> str:
    """
    Serializes a public key object to a PEM format string.
    """
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode('utf-8')

def deserialize_private_key(pem_str: str):
    """
    Deserializes a PEM private key string back into a PrivateKey object.
    """
    return serialization.load_pem_private_key(
        pem_str.encode('utf-8'),
        password=None,
        backend=default_backend()
    )

def deserialize_public_key(pem_str: str):
    """
    Deserializes a PEM public key string back into a PublicKey object.
    """
    return serialization.load_pem_public_key(
        pem_str.encode('utf-8'),
        backend=default_backend()
    )
