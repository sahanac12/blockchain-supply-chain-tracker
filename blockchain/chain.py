import time
from blockchain.block import Block, Transaction
from blockchain.validator import Validator

class Blockchain:
    def __init__(self):
        self.chain: list[Block] = []
        self.pending_transactions: list[Transaction] = []
        
        # State index: pkg_id -> latest_tx_id (to verify sequence quickly)
        self.package_states: dict[str, str] = {}
        
        # Keys Registry: category -> {entity_id: pub_key_pem_string}
        self.registry = {
            "beacons": {},
            "nodes": {},
            "authorities": {}
        }
        
        # Initialize Genesis Block
        self.create_genesis_block()

    def create_genesis_block(self):
        """
        Generates the first block (index 0) of the ledger.
        """
        genesis_block = Block(
            index=0,
            timestamp=int(time.time()),
            prev_block_hash="0" * 64,
            transactions=[]
        )
        # Genesis block does not require validation, but we pre-sign or mock it
        genesis_block.block_hash = genesis_block.calculate_hash()
        genesis_block.authority_sig = {
            "authority_node_id": "GENESIS",
            "signature": "0" * 128
        }
        self.chain.append(genesis_block)

    def add_beacon(self, beacon_id: str, public_key_pem: str):
        self.registry["beacons"][beacon_id] = public_key_pem

    def add_node(self, node_id: str, public_key_pem: str):
        self.registry["nodes"][node_id] = public_key_pem

    def add_authority(self, auth_id: str, public_key_pem: str):
        self.registry["authorities"][auth_id] = public_key_pem

    def get_package_last_hash(self, pkg_id: str, include_mempool: bool = False) -> str:
        """
        Gets the last transaction hash for a package, checking both the confirmed ledger and optionally the mempool.
        """
        if include_mempool:
            # First check the mempool (latest pending transaction)
            for tx in reversed(self.pending_transactions):
                if tx.pkg_id == pkg_id:
                    return tx.tx_id
        # Otherwise get from confirmed state
        return self.package_states.get(pkg_id, "0")

    def submit_transaction(self, tx_dict: dict) -> tuple[bool, str]:
        """
        Submits a transaction to the pending pool.
        Performs static checks (signatures, node existence) but does not commit 
        provenance checks yet since state can change before the block is mined.
        """
        try:
            tx = Transaction.from_dict(tx_dict)
            
            # Basic validation of signatures and registration
            node_key = self.registry["nodes"].get(tx.node_id)
            beacon_key = self.registry["beacons"].get(tx.beacon_id)
            
            if not node_key:
                return False, f"Logistics Node '{tx.node_id}' is not registered."
            if not beacon_key:
                return False, f"Location Beacon '{tx.beacon_id}' is not registered."
                
            if not Validator.verify_beacon_signature(tx, beacon_key):
                return False, "Invalid Beacon signature."
            if not Validator.verify_node_signature(tx, node_key):
                return False, "Invalid Node signature."
                
            # Add to memory pool
            self.pending_transactions.append(tx)
            return True, tx.tx_id
        except Exception as e:
            return False, f"Transaction submission failed: {str(e)}"

    def mine_pending_transactions(self, authority_id: str, authority_private_key, extra_keys: dict = None) -> tuple[bool, str]:
        """
        Aggregates pending transactions into a new block, validates their sequence,
        signs the block under PoA consensus, and updates ledger state.
        """
        if not self.pending_transactions:
            return False, "No pending transactions to mine."
            
        auth_key = self.registry["authorities"].get(authority_id)
        if not auth_key:
            return False, f"Consensus Authority '{authority_id}' is not registered."

        # Fetch parent block
        prev_block = self.chain[-1]
        
        # Build block
        new_block = Block(
            index=prev_block.index + 1,
            timestamp=int(time.time()),
            prev_block_hash=prev_block.block_hash,
            transactions=self.pending_transactions.copy()
        )
        
        # Sign block with main authority
        new_block.sign_block(authority_private_key, authority_id)
        
        # Sign with extra authorities for quorum
        if extra_keys:
            for extra_id, extra_key in extra_keys.items():
                if extra_id != authority_id:
                    new_block.sign_block(extra_key, extra_id)
        
        # Validate block complete sequence rules
        valid, err_msg = Validator.validate_block(
            new_block, 
            self.registry, 
            prev_block.block_hash, 
            self.get_package_last_hash
        )
        
        if not valid:
            return False, f"Consensus Validation Block Rejected: {err_msg}"
            
        # Commit to chain
        self.chain.append(new_block)
        
        # Update state index
        for tx in new_block.transactions:
            self.package_states[tx.pkg_id] = tx.tx_id
            
        # Clear pool
        self.pending_transactions = []
        return True, new_block.block_hash

    def get_package_history(self, pkg_id: str) -> list[dict]:
        """
        Traces the supply chain provenance history for a package backwards 
        via cryptographic transaction links (prev_proof_hash).
        """
        history = []
        latest_tx_id = self.package_states.get(pkg_id)
        if not latest_tx_id:
            return []

        # Map all transactions for rapid lookup
        tx_lookup = {}
        for block in self.chain:
            for tx in block.transactions:
                tx_lookup[tx.tx_id] = tx

        curr_tx_id = latest_tx_id
        visited = set()  # Prevent infinite loops if loop exists in attack

        while curr_tx_id and curr_tx_id != "0":
            if curr_tx_id in visited:
                break
            visited.add(curr_tx_id)
            
            tx = tx_lookup.get(curr_tx_id)
            if not tx:
                break
            history.append(tx.to_dict())
            curr_tx_id = tx.prev_proof_hash

        # Reverse to get chronological order (Manufacturer -> ... -> Consumer)
        history.reverse()
        return history
