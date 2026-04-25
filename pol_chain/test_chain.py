import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pol_chain.chain.block import PolBlock
from pol_chain.chain.blockchain import Blockchain
from pol_chain.nodes.node import Node
from pol_chain.utils.crypto import sign_data

def main():
    print("Testing Proof of Location Chain...")
    
    # 1. Create Nodes
    node1 = Node(name="Factory", location_name="Chennai, India", lat=13.0827, lon=80.2707)
    node2 = Node(name="Truck", location_name="On NH48 highway", lat=13.5, lon=79.8)

    # 2. Init Blockchain and add Genesis
    bc = Blockchain()
    genesis = bc.genesis_block()
    bc.chain.append(genesis)
    print(f"Added Genesis Block: {genesis.block_hash[:16]}...")

    # 3. Add Block 1
    pkg_id = "PKG123"
    prev_hash = bc.chain[-1].block_hash
    b1 = PolBlock(
        block_index=1,
        package_id=pkg_id,
        node_id=node1.node_id,
        node_name=node1.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        lat=node1.lat,
        lon=node1.lon,
        wifi_fingerprint=[{"bssid": "00:11:22:33:44", "rssi": -50, "ssid": "FACTORY_WIFI"}],
        prev_hash=prev_hash
    )
    b1.claim_hash = b1.compute_claim_hash()
    
    # Sign claim hash
    # For deterministic JSON dict signing logic expected by crypto.py, we pass a dict
    b1.signature = sign_data(node1.private_key_pem, {"claim_hash": b1.claim_hash})
    b1.block_hash = b1.compute_block_hash()
    
    if bc.add_block(b1):
        print(f"Added Block 1 from {node1.name}: {b1.block_hash[:16]}...")
    else:
        print("Failed to add Block 1")

    # 4. Add Block 2
    prev_hash = bc.chain[-1].block_hash
    b2 = PolBlock(
        block_index=2,
        package_id=pkg_id,
        node_id=node2.node_id,
        node_name=node2.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        lat=node2.lat,
        lon=node2.lon,
        wifi_fingerprint=[],
        prev_hash=prev_hash
    )
    b2.claim_hash = b2.compute_claim_hash()
    b2.signature = sign_data(node2.private_key_pem, {"claim_hash": b2.claim_hash})
    b2.block_hash = b2.compute_block_hash()
    
    if bc.add_block(b2):
         print(f"Added Block 2 from {node2.name}: {b2.block_hash[:16]}...")
    else:
        print("Failed to add Block 2")

    # 5. Verify Chain
    print("\nVerifying chain integrity...")
    is_valid, issues = bc.verify_chain()
    if is_valid:
        print("PASS")
    else:
        print("FAIL")
        print("Issues:", issues)

if __name__ == "__main__":
    main()
