from datetime import datetime, timezone
from typing import List, Tuple
from pol_chain.chain.block import PolBlock

class Blockchain:
    def __init__(self):
        self.chain: List[PolBlock] = []
        
    def genesis_block(self) -> PolBlock:
        b = PolBlock(
            block_index=0,
            package_id="GENESIS",
            node_id="ORIGIN",
            node_name="ORIGIN",
            timestamp=datetime.now(timezone.utc).isoformat(),
            lat=0.0,
            lon=0.0,
            wifi_fingerprint=[],
            prev_hash="0" * 64
        )
        b.claim_hash = b.compute_claim_hash()
        b.signature = "GENESIS_SIG"
        b.block_hash = b.compute_block_hash()
        return b
        
    def add_block(self, block: PolBlock) -> bool:
        if len(self.chain) > 0:
            prev_block = self.chain[-1]
            if block.prev_hash != prev_block.block_hash:
                return False
            if block.block_index != prev_block.block_index + 1:
                return False
                
        self.chain.append(block)
        return True
        
    def verify_chain(self) -> Tuple[bool, List[str]]:
        issues = []
        for i in range(len(self.chain)):
            block = self.chain[i]
            
            if block.compute_claim_hash() != block.claim_hash:
                issues.append(f"Block {block.block_index} has invalid claim_hash")
                
            if block.compute_block_hash() != block.block_hash:
                issues.append(f"Block {block.block_index} has invalid block_hash")
                
            if i > 0:
                prev_block = self.chain[i-1]
                if block.prev_hash != prev_block.block_hash:
                    issues.append(f"Block {block.block_index} prev_hash does not match previous block hash")
                    
        return len(issues) == 0, issues
        
    def to_dict(self) -> dict:
        return {
            "chain": [b.to_dict() for b in self.chain]
        }
        
    @classmethod
    def from_dict(cls, d: dict) -> 'Blockchain':
        bc = cls()
        for b_data in d.get("chain", []):
            bc.chain.append(PolBlock.from_dict(b_data))
        return bc
