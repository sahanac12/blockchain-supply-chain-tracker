import time
from crypto.keys import generate_key_pair, serialize_public_key, serialize_private_key
from crypto.signatures import sign_data

class LocalAttestationBeacon:
    def __init__(self, beacon_id: str, lat: float, lon: float, private_key=None):
        self.beacon_id = beacon_id
        self.lat = lat
        self.lon = lon
        
        # If no key is provided, generate a new one for this beacon
        if private_key is None:
            self.private_key, self.public_key = generate_key_pair()
        else:
            self.private_key = private_key
            self.public_key = private_key.public_key()

    def get_public_key_pem(self) -> str:
        """
        Returns public key in PEM format.
        """
        return serialize_public_key(self.public_key)

    def get_private_key_pem(self) -> str:
        """
        Returns private key in PEM format.
        """
        return serialize_private_key(self.private_key)

    def generate_attestation_token(self, custom_time: int = None, lat: float = None, lon: float = None) -> dict:
        """
        Generates a rolling Location Attestation Token (LAT) containing coordinates, 
        current timestamp, and beacon's digital signature.
        """
        timestamp = custom_time if custom_time is not None else int(time.time())
        lat_val = lat if lat is not None else self.lat
        lon_val = lon if lon is not None else self.lon
        
        # Format: beacon_id:lat:lon:timestamp
        data_to_sign = f"{self.beacon_id}:{lat_val}:{lon_val}:{timestamp}"
        
        signature = sign_data(self.private_key, data_to_sign.encode('utf-8'))
        
        return {
            "beacon_id": self.beacon_id,
            "location": {
                "lat": lat_val,
                "lon": lon_val
            },
            "epoch_time": timestamp,
            "beacon_sig": signature
        }
