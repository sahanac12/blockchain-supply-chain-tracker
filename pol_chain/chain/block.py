import json
import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Union

@dataclass
class PolBlock:
    block_index: int
    package_id: str
    node_id: str
    node_name: str
    timestamp: str
    lat: float
    lon: float
    wifi_fingerprint: List[Dict[str, Union[str, int]]]
    prev_hash: str
    claim_hash: str = ""
    signature: str = ""
    block_hash: str = ""
    flagged: bool = False
    flag_reason: str = ""
    
    def compute_claim_hash(self) -> str:
        claim_data = {
            "package_id": self.package_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "lat": self.lat,
            "lon": self.lon,
            "wifi_fingerprint": self.wifi_fingerprint
        }
        claim_str = json.dumps(claim_data, sort_keys=True).encode('utf-8')
        return hashlib.sha256(claim_str).hexdigest()
        
    def compute_block_hash(self) -> str:
        block_data = self.to_dict()
        # Remove block_hash from data to hash so it doesn't try to hash itself
        if "block_hash" in block_data:
            del block_data["block_hash"]
            
        block_str = json.dumps(block_data, sort_keys=True).encode('utf-8')
        return hashlib.sha256(block_str).hexdigest()
        
    def to_dict(self) -> dict:
        return asdict(self)
        
    @classmethod
    def from_dict(cls, d: dict) -> 'PolBlock':
        return cls(**d)
