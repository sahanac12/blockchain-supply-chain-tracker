import json
from blockchain.block import Transaction, Block
from crypto.signatures import verify_signature
from crypto.keys import deserialize_public_key
from crypto.hashing import MerkleTree

class Validator:
    @staticmethod
    def verify_beacon_signature(tx: Transaction, beacon_pub_key_pem: str) -> bool:
        """
        Verifies the beacon signature on the location attestation metadata.
        """
        try:
            pub_key = deserialize_public_key(beacon_pub_key_pem)
            # Reconstruct the beacon signed payload
            beacon_data = f"{tx.beacon_id}:{tx.location['lat']}:{tx.location['lon']}:{tx.epoch_time}"
            return verify_signature(pub_key, tx.beacon_sig, beacon_data.encode('utf-8'))
        except Exception:
            return False

    @staticmethod
    def verify_node_signature(tx: Transaction, node_pub_key_pem: str) -> bool:
        """
        Verifies the logistics node's signature on the entire Proof-of-Location record.
        """
        try:
            pub_key = deserialize_public_key(node_pub_key_pem)
            # Reconstruct the node signed payload (excluding node's own signature)
            signing_dict = tx.get_signing_data()
            node_data = json.dumps(signing_dict, sort_keys=True, default=str)
            return verify_signature(pub_key, tx.node_sig, node_data.encode('utf-8'))
        except Exception:
            return False

    @classmethod
    def validate_transaction(cls, tx: Transaction, registry: dict, package_last_hash: str) -> tuple[bool, str]:
        """
        Validates a single Proof-of-Location transaction.
        Checks node signature, beacon signature, and supply chain provenance continuity.
        """
        # 1. Check if Node is registered
        node_key = registry.get("nodes", {}).get(tx.node_id)
        if not node_key:
            return False, f"Logistics Node '{tx.node_id}' is not registered."

        # 2. Check if Beacon is registered
        beacon_key = registry.get("beacons", {}).get(tx.beacon_id)
        if not beacon_key:
            return False, f"Location Beacon '{tx.beacon_id}' is not registered."

        # 3. Verify Beacon Signature
        if not cls.verify_beacon_signature(tx, beacon_key):
            return False, f"Invalid Beacon signature for transaction {tx.tx_id}."

        # 4. Verify Node Signature
        if not cls.verify_node_signature(tx, node_key):
            return False, f"Invalid Node signature for transaction {tx.tx_id}."

        # 5. Verify Provenance Linkage (Sequence Continuity)
        # package_last_hash is the hash of the package's previous tx. 
        # If it's a new package, the prev_proof_hash must be "0".
        expected_prev = package_last_hash if package_last_hash else "0"
        if tx.prev_proof_hash != expected_prev:
            return False, (
                f"Provenance chain broken for package {tx.pkg_id}. "
                f"Transaction references prev_hash '{tx.prev_proof_hash}', "
                f"but ledger expected '{expected_prev}'."
            )

        # 6. Verify Temporal Freshness (Freshness Check)
        # Ensure epoch_time is not in the past by more than 5 minutes (300 seconds)
        import time
        current_time = int(time.time())
        if (current_time - tx.epoch_time) > 300:
            return False, (
                f"Transaction attestation has expired. "
                f"Timestamp {tx.epoch_time} is older than allowed 300-second freshness limit."
            )
        if (tx.epoch_time - current_time) > 60:
            return False, f"Transaction attestation timestamp {tx.epoch_time} is in the future."

        return True, "Valid"

    @classmethod
    def validate_block(cls, block: Block, registry: dict, prev_block_hash: str, 
                       get_package_last_hash_func) -> tuple[bool, str]:
        """
        Validates a block in the ledger, verifying consensus signature, hashes, 
        and all contained Proof-of-Location transactions.
        """
        # 1. Verify block header matches hash
        if block.block_hash != block.calculate_hash():
            return False, "Block hash mismatch."

        # 2. Verify previous block hash link
        if block.prev_block_hash != prev_block_hash:
            return False, f"Prev block hash mismatch. Expected {prev_block_hash}, got {block.prev_block_hash}."

        # 3. Verify Merkle Root
        tx_hashes = [tx.tx_id for tx in block.transactions]
        calculated_root = MerkleTree(tx_hashes).get_root()
        if block.merkle_root != calculated_root:
            return False, "Merkle Root mismatch."

        # 4. Verify Authority Consensus Signatures (PoA Quorum Verification)
        # If no signatures exist, reject.
        if not hasattr(block, "authority_sigs") or not block.authority_sigs:
            return False, "Block is missing Proof-of-Authority (PoA) signatures."
            
        registered_authorities = registry.get("authorities", {})
        
        # Calculate required quorum size: majority of registered authorities
        # If registry has none or only 1, the quorum size is 1.
        total_authorities = len(registered_authorities)
        required_quorum = (total_authorities // 2) + 1 if total_authorities > 0 else 1
        
        valid_signatures_count = 0
        verified_authority_ids = set()
        
        for sig_dict in block.authority_sigs:
            auth_id = sig_dict.get("authority_node_id")
            auth_sig = sig_dict.get("signature")
            
            # Prevent duplicate signatures from the same authority counting twice
            if auth_id in verified_authority_ids:
                continue
                
            auth_key = registered_authorities.get(auth_id)
            if not auth_key:
                # Support Genesis blocks where authority ID is 'GENESIS'
                if auth_id == "GENESIS":
                    valid_signatures_count += 1
                    verified_authority_ids.add(auth_id)
                    continue
                return False, f"Validator Authority '{auth_id}' is not registered."
                
            try:
                pub_key = deserialize_public_key(auth_key)
                if verify_signature(pub_key, auth_sig, block.block_hash.encode('utf-8')):
                    valid_signatures_count += 1
                    verified_authority_ids.add(auth_id)
            except Exception as e:
                return False, f"Failed to verify authority signature for '{auth_id}': {str(e)}"
                
        if valid_signatures_count < required_quorum:
            return False, (
                f"Consensus Quorum Verification Failed: Got {valid_signatures_count} valid PoA signatures, "
                f"but consensus rules require at least {required_quorum} out of {total_authorities} registered authorities."
            )

        # 5. Verify all transactions in block
        # We need to simulate the state updating *within* the block to ensure transaction chains
        # within the same block are also sequentially valid.
        temp_state = {}
        for tx in block.transactions:
            # Query current ledger state or temporary block-level state
            current_head = temp_state.get(tx.pkg_id)
            if current_head is None:
                current_head = get_package_last_hash_func(tx.pkg_id)
            
            valid, msg = cls.validate_transaction(tx, registry, current_head)
            if not valid:
                return False, f"Tx Validation Failed for {tx.tx_id}: {msg}"
            
            # Apply state update locally
            temp_state[tx.pkg_id] = tx.tx_id

        return True, "Valid"
