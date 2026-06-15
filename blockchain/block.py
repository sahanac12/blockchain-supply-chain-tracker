import time
from crypto.hashing import hash_dict, MerkleTree

class Transaction:
    def __init__(self, pkg_id: str, node_id: str, beacon_id: str, location: dict, 
                 epoch_time: int, prev_proof_hash: str, beacon_sig: str, 
                 node_sig: str = None, tx_id: str = None):
        self.pkg_id = pkg_id
        self.node_id = node_id
        self.beacon_id = beacon_id
        self.location = location  # {"lat": float, "lon": float}
        self.epoch_time = int(epoch_time)
        self.prev_proof_hash = prev_proof_hash
        self.beacon_sig = beacon_sig
        self.node_sig = node_sig
        
        # Calculate tx_id if not provided
        self.tx_id = tx_id if tx_id else self.calculate_hash()

    def get_signing_data(self) -> dict:
        """
        Returns the data dictionary that the logistics node signs.
        Note that this does NOT include the node_sig, but DOES include beacon_sig.
        """
        return {
            "pkg_id": self.pkg_id,
            "node_id": self.node_id,
            "beacon_id": self.beacon_id,
            "location": self.location,
            "epoch_time": self.epoch_time,
            "prev_proof_hash": self.prev_proof_hash,
            "beacon_sig": self.beacon_sig
        }

    def calculate_hash(self) -> str:
        """
        Computes SHA-256 hash of the transaction contents.
        """
        return hash_dict(self.to_dict(include_sigs=True))

    def to_dict(self, include_sigs=True) -> dict:
        d = {
            "pkg_id": self.pkg_id,
            "node_id": self.node_id,
            "beacon_id": self.beacon_id,
            "location": self.location,
            "epoch_time": self.epoch_time,
            "prev_proof_hash": self.prev_proof_hash,
        }
        if include_sigs:
            d["beacon_sig"] = self.beacon_sig
            d["node_sig"] = self.node_sig
            if hasattr(self, "tx_id"):
                d["tx_id"] = self.tx_id
        return d

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pkg_id=d["pkg_id"],
            node_id=d["node_id"],
            beacon_id=d["beacon_id"],
            location=d["location"],
            epoch_time=d["epoch_time"],
            prev_proof_hash=d["prev_proof_hash"],
            beacon_sig=d.get("beacon_sig"),
            node_sig=d.get("node_sig"),
            tx_id=d.get("tx_id")
        )


class Block:
    def __init__(self, index: int, timestamp: int, prev_block_hash: str, 
                 transactions: list, merkle_root: str = None, 
                 authority_sig: dict = None, authority_sigs: list = None,
                 block_hash: str = None):
        self.index = index
        self.timestamp = int(timestamp)
        self.prev_block_hash = prev_block_hash
        self.transactions = [
            Transaction.from_dict(tx) if isinstance(tx, dict) else tx 
            for tx in transactions
        ]
        
        # Compute Merkle root if not specified
        if merkle_root is None:
            tx_hashes = [tx.tx_id for tx in self.transactions]
            self.merkle_root = MerkleTree(tx_hashes).get_root()
        else:
            self.merkle_root = merkle_root
            
        self.authority_sigs = authority_sigs if authority_sigs is not None else ([authority_sig] if authority_sig is not None else [])
        self.block_hash = block_hash if block_hash else self.calculate_hash()

    def get_header(self) -> dict:
        """
        Returns the block header data structure which defines the block hash.
        """
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_block_hash": self.prev_block_hash,
            "merkle_root": self.merkle_root
        }

    def calculate_hash(self) -> str:
        """
        Calculates the block hash by hashing the header.
        """
        return hash_dict(self.get_header())

    def sign_block(self, authority_private_key, authority_node_id: str):
        """
        Signs the block hash with the authority's private key and appends it to authority_sigs.
        """
        from crypto.signatures import sign_data
        self.block_hash = self.calculate_hash()
        sig = {
            "authority_node_id": authority_node_id,
            "signature": sign_data(authority_private_key, self.block_hash.encode('utf-8'))
        }
        self.authority_sigs = [s for s in self.authority_sigs if s["authority_node_id"] != authority_node_id]
        self.authority_sigs.append(sig)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_block_hash": self.prev_block_hash,
            "merkle_root": self.merkle_root,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "authority_sig": self.authority_sigs[0] if self.authority_sigs else None,
            "authority_sigs": self.authority_sigs,
            "block_hash": self.block_hash
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            index=d["index"],
            timestamp=d["timestamp"],
            prev_block_hash=d["prev_block_hash"],
            transactions=[Transaction.from_dict(tx) for tx in d["transactions"]],
            merkle_root=d.get("merkle_root"),
            authority_sig=d.get("authority_sig"),
            authority_sigs=d.get("authority_sigs"),
            block_hash=d.get("block_hash")
        )
