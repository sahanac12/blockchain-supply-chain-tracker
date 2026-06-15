import pytest
import time
from crypto.keys import generate_key_pair, serialize_public_key
from crypto.signatures import sign_data
from node.beacon import LocalAttestationBeacon
from node.gateway import LogisticsGateway
from blockchain.chain import Blockchain
from blockchain.block import Transaction, Block
from blockchain.validator import Validator

@pytest.fixture
def test_env():
    """
    Sets up a standard testing environment with 1 beacon, 1 node, and 1 authority.
    """
    blockchain = Blockchain()
    
    # Register beacon & node
    beacon = LocalAttestationBeacon("BEACON-TEST", 40.7128, -74.0060)
    node = LogisticsGateway("NODE-TEST")
    
    blockchain.add_beacon(beacon.beacon_id, beacon.get_public_key_pem())
    blockchain.add_node(node.node_id, node.get_public_key_pem())
    
    # Register authority
    auth_priv, auth_pub = generate_key_pair()
    auth_id = "AUTH-MAIN"
    blockchain.add_authority(auth_id, serialize_public_key(auth_pub))
    
    return blockchain, beacon, node, (auth_id, auth_priv)

def test_signature_tampering_fails(test_env):
    blockchain, beacon, node, (auth_id, auth_priv) = test_env
    pkg_id = "PKG-ATTACK-01"
    
    token = beacon.generate_attestation_token()
    tx_dict = node.create_proof_of_location(pkg_id, token, "0")
    
    # Tamper with signature
    tx_dict["node_sig"] = tx_dict["node_sig"][:-4] + "ffff"
    
    success, res = blockchain.submit_transaction(tx_dict)
    assert success is False
    assert "Invalid Node signature" in res

def test_coordinate_forgery_fails(test_env):
    blockchain, beacon, node, (auth_id, auth_priv) = test_env
    pkg_id = "PKG-ATTACK-02"
    
    # Beacon emits token for NYC coordinates (40.7128, -74.0060)
    token = beacon.generate_attestation_token()
    
    # Malicious node alters coordinates to London (51.5074, -0.1278)
    token["location"] = {"lat": 51.5074, "lon": -0.1278}
    
    tx_dict = node.create_proof_of_location(pkg_id, token, "0")
    
    # Attempt to submit
    success, res = blockchain.submit_transaction(tx_dict)
    assert success is False
    assert "Invalid Beacon signature" in res

def test_fork_attack_blocks_mining(test_env):
    blockchain, beacon, node, (auth_id, auth_priv) = test_env
    pkg_id = "PKG-ATTACK-03"
    
    # Setup second node & beacon
    beacon_other = LocalAttestationBeacon("BEACON-OTHER", 34.0522, -118.2437)
    node_other = LogisticsGateway("NODE-OTHER")
    blockchain.add_beacon(beacon_other.beacon_id, beacon_other.get_public_key_pem())
    blockchain.add_node(node_other.node_id, node_other.get_public_key_pem())
    
    # 1. First location proof referencing "0"
    token1 = beacon.generate_attestation_token()
    tx1 = node.create_proof_of_location(pkg_id, token1, "0")
    
    # 2. Second location proof (Double-location) also referencing "0" (representing split state)
    token2 = beacon_other.generate_attestation_token()
    tx2 = node_other.create_proof_of_location(pkg_id, token2, "0")
    
    # Both signatures check out, so they are allowed into the memory pool
    s1, r1 = blockchain.submit_transaction(tx1)
    s2, r2 = blockchain.submit_transaction(tx2)
    assert s1 is True
    assert s2 is True
    assert len(blockchain.pending_transactions) == 2
    
    # Attempt to mine block
    mine_success, msg = blockchain.mine_pending_transactions(auth_id, auth_priv)
    
    # Mining must fail because validator checks transaction sequence rules and catches the fork!
    assert mine_success is False
    assert "Provenance chain broken" in msg

def test_replay_attack_rejected_on_freshness(test_env):
    blockchain, beacon, node, (auth_id, auth_priv) = test_env
    pkg_id = "PKG-ATTACK-04"
    
    # Generate a transaction using an expired epoch (timestamp 10 minutes ago)
    old_time = int(time.time()) - 600
    expired_token = beacon.generate_attestation_token(custom_time=old_time)
    
    tx_dict = node.create_proof_of_location(pkg_id, expired_token, "0")
    
    # If the transaction is submitted, it is added to pool because beacon/node keys are valid.
    success, res = blockchain.submit_transaction(tx_dict)
    assert success is True
    
    # Let's perform validation checks as they would run on block level
    # Inside the block validator:
    # A block validator can enforce that the epoch timestamp of the transactions
    # is close to block creation timestamp. Let's verify that a validator catches it.
    
    # Let's verify that the block validator rejects blocks containing transactions with stale epoch times.
    # Note: to test this, our block validator in validator.py checks temporal freshness.
    # Let's check Validator.validate_block
    prev_block = blockchain.chain[-1]
    new_block = Block(
        index=prev_block.index + 1,
        timestamp=int(time.time()),
        prev_block_hash=prev_block.block_hash,
        transactions=blockchain.pending_transactions
    )
    new_block.sign_block(auth_priv, auth_id)
    
    # Validate the block containing the replayed transaction
    valid, msg = Validator.validate_block(
        new_block,
        blockchain.registry,
        prev_block.block_hash,
        blockchain.get_package_last_hash
    )
    
    assert valid is False
    assert "Transaction attestation has expired" in msg

def test_quarantine_flow(test_env):
    blockchain, beacon, node, (auth_id, auth_priv) = test_env
    pkg_id = "PKG-ATTACK-05"
    
    # Setup second node & beacon
    beacon_other = LocalAttestationBeacon("BEACON-OTHER", 34.0522, -118.2437)
    node_other = LogisticsGateway("NODE-OTHER")
    blockchain.add_beacon(beacon_other.beacon_id, beacon_other.get_public_key_pem())
    blockchain.add_node(node_other.node_id, node_other.get_public_key_pem())
    
    # Legit transaction
    token1 = beacon.generate_attestation_token()
    tx1 = node.create_proof_of_location(pkg_id, token1, "0")
    
    # Malicious transaction (cloned prev_proof_hash)
    token2 = beacon_other.generate_attestation_token()
    tx2 = node_other.create_proof_of_location(pkg_id, token2, "0")
    
    # Submit both to mempool
    s1, r1 = blockchain.submit_transaction(tx1)
    s2, r2 = blockchain.submit_transaction(tx2)
    assert s1 is True
    assert s2 is True
    assert len(blockchain.pending_transactions) == 2
    
    # Find and quarantine the malicious transaction (r2)
    found_tx = None
    for tx in blockchain.pending_transactions:
        if tx.tx_id == r2:
            found_tx = tx
            break
    assert found_tx is not None
    
    blockchain.pending_transactions.remove(found_tx)
    assert len(blockchain.pending_transactions) == 1
    assert blockchain.pending_transactions[0].tx_id == r1
    
    # Mining should succeed since the fork transaction has been quarantined
    mine_success, msg = blockchain.mine_pending_transactions(auth_id, auth_priv)
    assert mine_success is True
    assert len(blockchain.chain) == 2

