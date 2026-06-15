import json
import time
from crypto.keys import generate_key_pair, serialize_public_key, serialize_private_key
from crypto.signatures import sign_data
from blockchain.block import Transaction

class LogisticsGateway:
    def __init__(self, node_id: str, private_key=None):
        self.node_id = node_id
        
        # If no key is provided, generate a new one
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

    def create_proof_of_location(self, pkg_id: str, beacon_token: dict, 
                                  prev_proof_hash: str, custom_time: int = None) -> dict:
        """
        Constructs a complete Transaction representing a Proof-of-Location.
        Signs the record with the logistics node's private key.
        """
        # Create transaction model (which generates tx_id internally)
        tx = Transaction(
            pkg_id=pkg_id,
            node_id=self.node_id,
            beacon_id=beacon_token["beacon_id"],
            location=beacon_token["location"],
            epoch_time=beacon_token["epoch_time"],
            prev_proof_hash=prev_proof_hash,
            beacon_sig=beacon_token["beacon_sig"]
        )
        
        # Compile node sign payload (excluding signature but including beacon signature)
        signing_dict = tx.get_signing_data()
        
        # Deterministic serialization
        serialized_data = json.dumps(signing_dict, sort_keys=True, default=str)
        
        # Sign transaction using node's private key
        node_sig = sign_data(self.private_key, serialized_data.encode('utf-8'))
        
        # Attach signature and update transaction id
        tx.node_sig = node_sig
        tx.tx_id = tx.calculate_hash()
        
        return tx.to_dict()
