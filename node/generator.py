import time
from crypto.keys import generate_key_pair, serialize_public_key
from node.beacon import LocalAttestationBeacon
from node.gateway import LogisticsGateway
from blockchain.chain import Blockchain

# Define geographical route coordinates inside the Bangalore area
ROUTE_TEMPLATES = {
    "standard_delivery": [
        {"id": "101", "name": "Electronic City Warehouse", "lat": 12.8399, "lon": 77.6770},
        {"id": "102", "name": "Silk Board Route Transit", "lat": 12.9176, "lon": 77.6244},
        {"id": "103", "name": "Indiranagar Retail Store", "lat": 12.9784, "lon": 77.6408}
    ],
    "electronics_import": [
        {"id": "201", "name": "Peenya Manufacturing Plant", "lat": 13.0284, "lon": 77.5197},
        {"id": "202", "name": "Yeshwanthpur Cargo Depot", "lat": 13.0235, "lon": 77.5580},
        {"id": "203", "name": "Outer Ring Road Cargo Hub", "lat": 12.9304, "lon": 77.6853},
        {"id": "204", "name": "Whitefield Distribution Center", "lat": 12.9698, "lon": 77.7499},
        {"id": "205", "name": "MG Road Flagship Store", "lat": 12.9738, "lon": 77.6119}
    ],
    "pharmaceuticals_cold_chain": [
        {"id": "301", "name": "Bommasandra Biotech Lab", "lat": 12.8094, "lon": 77.6917},
        {"id": "302", "name": "Kempegowda Airport Terminal", "lat": 13.1986, "lon": 77.7066},
        {"id": "303", "name": "Hebbal Logistics Depot", "lat": 13.0359, "lon": 77.5970},
        {"id": "304", "name": "Majestic Transit Terminal", "lat": 12.9756, "lon": 77.5728},
        {"id": "305", "name": "Jayanagar Care Pharmacy", "lat": 12.9299, "lon": 77.5824}
    ]
}

def setup_simulation_environment() -> tuple[Blockchain, dict, dict, tuple[str, any], dict]:
    """
    Sets up a clean blockchain, registers beacons and logistics nodes, 
    and returns a pre-configured simulation environment.
    """
    blockchain = Blockchain()
    
    beacons = {}
    nodes = {}
    
    # Setup local template beacons and nodes
    for route_name, route_steps in ROUTE_TEMPLATES.items():
        for step in route_steps:
            step_id = step["id"]
            beacon = LocalAttestationBeacon(f"BEACON-{step_id}", step["lat"], step["lon"])
            node = LogisticsGateway(f"NODE-{step_id}")
            beacons[beacon.beacon_id] = beacon
            nodes[node.node_id] = node

    # 2. Setup Authority Validators
    auth_private_key, auth_public_key = generate_key_pair()
    auth_id = "AUTHORITY-MAIN"
    blockchain.add_authority(auth_id, serialize_public_key(auth_public_key))
    
    authority_keys = {auth_id: auth_private_key}
    for extra_id in ["AUTHORITY-PRODUCER", "AUTHORITY-CARRIER", "AUTHORITY-RETAILER"]:
        priv, pub = generate_key_pair()
        blockchain.add_authority(extra_id, serialize_public_key(pub))
        authority_keys[extra_id] = priv
        
    authority_info = (auth_id, auth_private_key, authority_keys)
    
    # Return environment items
    return blockchain, beacons, nodes, authority_info, ROUTE_TEMPLATES

def simulate_step(blockchain: Blockchain, beacons: dict, nodes: dict, 
                  pkg_id: str, route_step: dict, custom_time: int = None) -> tuple[bool, str]:
    """
    Simulates a single package scan at a specific supply chain route step.
    Generates a PoL transaction and submits it to the blockchain.
    """
    step_id = route_step["id"]
    beacon_id = f"BEACON-{step_id}"
    node_id = f"NODE-{step_id}"
    
    beacon: LocalAttestationBeacon = beacons.get(beacon_id)
    node: LogisticsGateway = nodes.get(node_id)
    
    if not beacon or not node:
        # Lazy dynamic initialization for custom routes
        if not beacon:
            beacon = LocalAttestationBeacon(beacon_id, route_step.get("lat", 0.0), route_step.get("lon", 0.0))
            beacons[beacon_id] = beacon
        if not node:
            node = LogisticsGateway(node_id)
            nodes[node_id] = node
        
    # Dynamically register keys in blockchain registry if not present
    if beacon_id not in blockchain.registry["beacons"]:
        blockchain.add_beacon(beacon_id, beacon.get_public_key_pem())
    if node_id not in blockchain.registry["nodes"]:
        blockchain.add_node(node_id, node.get_public_key_pem())
        
    # Get previous proof hash from blockchain for this package
    prev_hash = blockchain.get_package_last_hash(pkg_id, include_mempool=True)
    
    # Beacon emits attestation token
    beacon_token = beacon.generate_attestation_token(
        custom_time=custom_time,
        lat=route_step.get("lat"),
        lon=route_step.get("lon")
    )
    
    # Node builds and signs Proof-of-Location transaction
    tx_dict = node.create_proof_of_location(
        pkg_id=pkg_id,
        beacon_token=beacon_token,
        prev_proof_hash=prev_hash,
        custom_time=custom_time
    )
    
    # Submit to mempool
    success, res = blockchain.submit_transaction(tx_dict)
    return success, res
