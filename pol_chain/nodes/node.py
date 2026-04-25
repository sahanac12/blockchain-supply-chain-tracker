import uuid
from pol_chain.utils.crypto import generate_keypair

class Node:
    def __init__(self, name: str, location_name: str, lat: float, lon: float, node_id: str = None):
        self.node_id = node_id if node_id is not None else str(uuid.uuid4())
        self.name = name
        self.location_name = location_name
        self.lat = lat
        self.lon = lon
        self.private_key_pem, self.public_key_pem = generate_keypair()
        
    def to_public_dict(self):
        # We decode public key if it is bytes, to ensure JSON serializability
        pub_key = self.public_key_pem.decode('utf-8') if isinstance(self.public_key_pem, bytes) else self.public_key_pem
        return {
            "node_id": self.node_id,
            "name": self.name,
            "location_name": self.location_name,
            "lat": self.lat,
            "lon": self.lon,
            "public_key_pem": pub_key
        }
