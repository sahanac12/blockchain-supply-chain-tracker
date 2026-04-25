import json
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

def generate_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_key_pem, public_key_pem

def _serialize_data(data_dict):
    return json.dumps(data_dict, sort_keys=True).encode('utf-8')

def sign_data(private_key_pem, data_dict):
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None
    )
    
    data = _serialize_data(data_dict)
    
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    return base64.b64encode(signature).decode('utf-8')

def verify_signature(public_key_pem, data_dict, signature_b64):
    public_key = serialization.load_pem_public_key(public_key_pem)
    data = _serialize_data(data_dict)
    signature = base64.b64decode(signature_b64)
    
    try:
        public_key.verify(
            signature,
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False
