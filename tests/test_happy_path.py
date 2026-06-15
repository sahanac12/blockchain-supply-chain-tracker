import pytest
import time
from crypto.keys import generate_key_pair, serialize_public_key, deserialize_public_key
from crypto.signatures import sign_data, verify_signature
from crypto.hashing import MerkleTree, hash_dict
from node.beacon import LocalAttestationBeacon
from node.gateway import LogisticsGateway
from blockchain.chain import Blockchain
from blockchain.block import Transaction, Block
from blockchain.validator import Validator

def test_keys_and_signatures():
    # 1. Generate keys
    priv_key, pub_key = generate_key_pair()
    
    # 2. Serialize / Deserialize keys
    priv_pem = serialize_public_key(pub_key)
    deserialized_pub = deserialize_public_key(priv_pem)
    
    # 3. Sign & Verify
    data = b"Verify my location coordinates!"
    sig = sign_data(priv_key, data)
    assert verify_signature(deserialized_pub, sig, data) is True
    
    # 4. Alter data and verify failure
    assert verify_signature(deserialized_pub, sig, data + b"extra") is False

def test_merkle_tree():
    # Construct leaf hashes
    leaves = [hash_dict({"tx": 1}), hash_dict({"tx": 2}), hash_dict({"tx": 3})]
    
    # Build tree
    tree = MerkleTree(leaves)
    root = tree.get_root()
    assert len(root) == 64
    
    # Generate proof for index 1
    proof = tree.get_proof(1)
    
    # Verify proof
    assert MerkleTree.verify_proof(leaves[1], proof, root) is True
    
    # Verify wrong proof leaf
    assert MerkleTree.verify_proof(leaves[0], proof, root) is False

def test_happy_path_supply_chain():
    # Initialize blockchain
    blockchain = Blockchain()
    
    # Register beacons & nodes
    beacon_wh = LocalAttestationBeacon("BEACON-WHSE-A", 37.7749, -122.4194)
    node_wh = LogisticsGateway("NODE-WHSE-A")
    blockchain.add_beacon(beacon_wh.beacon_id, beacon_wh.get_public_key_pem())
    blockchain.add_node(node_wh.node_id, node_wh.get_public_key_pem())
    
    # Register authority validator
    auth_priv, auth_pub = generate_key_pair()
    auth_id = "AUTH-MAIN"
    blockchain.add_authority(auth_id, serialize_public_key(auth_pub))
    
    # Package details
    pkg_id = "PKG-TEST-001"
    
    # STEP 1: Scan at Warehouse A
    beacon_token = beacon_wh.generate_attestation_token()
    tx_dict = node_wh.create_proof_of_location(
        pkg_id=pkg_id,
        beacon_token=beacon_token,
        prev_proof_hash="0"
    )
    
    # Submit transaction
    success, tx_id = blockchain.submit_transaction(tx_dict)
    assert success is True
    assert len(blockchain.pending_transactions) == 1
    
    # Mine block
    mine_success, block_hash = blockchain.mine_pending_transactions(auth_id, auth_priv)
    assert mine_success is True
    assert len(blockchain.chain) == 2  # Genesis + Block 1
    assert len(blockchain.pending_transactions) == 0
    assert blockchain.package_states[pkg_id] == tx_id
    
    # Verify provenance history length
    history = blockchain.get_package_history(pkg_id)
    assert len(history) == 1
    assert history[0]["node_id"] == "NODE-WHSE-A"
    assert history[0]["prev_proof_hash"] == "0"
