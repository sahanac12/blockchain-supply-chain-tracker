from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import json
from blockchain.chain import Blockchain
from blockchain.block import Block, Transaction
from blockchain.validator import Validator
from node.generator import setup_simulation_environment, simulate_step, ROUTE_TEMPLATES
from crypto.keys import deserialize_private_key, serialize_private_key, generate_key_pair
from crypto.signatures import sign_data
from node.beacon import LocalAttestationBeacon
from node.gateway import LogisticsGateway

app = FastAPI(
    title="POL Provenance API",
    description="REST API for cryptographic POL ledger in supply chain tracking.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the global simulation environment
blockchain, beacons, nodes, authority_info, routes = setup_simulation_environment()
auth_id, auth_private_key, authority_keys = authority_info

# Keep track of active packages in our simulation: pkg_id -> { "route_name": str, "current_step_index": int }
simulated_packages = {}

# Keep track of quarantined transactions flagged as attacks
quarantined_transactions = []

# Pydantic models for request bodies
class RegisterEntity(BaseModel):
    entity_type: str  # "beacons", "nodes", "authorities"
    entity_id: str
    public_key_pem: str

class SubmitTransactionModel(BaseModel):
    pkg_id: str
    node_id: str
    beacon_id: str
    location: dict  # {"lat": float, "lon": float}
    epoch_time: int
    prev_proof_hash: str
    beacon_sig: str
    node_sig: str

class SimulateStepRequest(BaseModel):
    pkg_id: str
    route_name: str
    latitude: float = None
    longitude: float = None

class MineRequest(BaseModel):
    authority_id: str = "AUTHORITY-MAIN"
    # To keep simple, if private_key_pem is empty, we will use the simulated global authority's key
    authority_private_key_pem: str = ""

class CustomRouteStep(BaseModel):
    id: str
    name: str
    lat: float
    lon: float

class CustomRouteRequest(BaseModel):
    route_name: str
    steps: list[CustomRouteStep]

@app.post("/routes")
def register_custom_route(data: CustomRouteRequest):
    global ROUTE_TEMPLATES
    ROUTE_TEMPLATES[data.route_name] = [step.model_dump() for step in data.steps]
    return {"status": "success", "message": f"Custom route '{data.route_name}' registered successfully."}

@app.post("/reset-ledger")
def reset_ledger_endpoint():
    global blockchain, simulated_packages, quarantined_transactions
    # Reset simulated package list and custom routes
    simulated_packages.clear()
    quarantined_transactions.clear()
    
    # Remove custom routes from ROUTE_TEMPLATES
    for route in list(ROUTE_TEMPLATES.keys()):
        if route not in ["standard_delivery", "electronics_import", "pharmaceuticals_cold_chain"]:
            del ROUTE_TEMPLATES[route]
    
    # Re-initialize the blockchain ledger properties
    blockchain.chain = []
    blockchain.pending_transactions = []
    blockchain.package_states.clear()
    blockchain.registry["beacons"].clear()
    blockchain.registry["nodes"].clear()
    blockchain.create_genesis_block()
    
    return {"status": "success", "message": "Blockchain ledger, custom routes, and simulation state have been reset."}

@app.get("/status")
def home():
    return {
        "status": "online",
        "system": "POL Supply Chain Tracker",
        "blocks_count": len(blockchain.chain),
        "pending_transactions_count": len(blockchain.pending_transactions),
        "registered_beacons": len(blockchain.registry["beacons"]),
        "registered_nodes": len(blockchain.registry["nodes"])
    }

@app.get("/chain")
def get_chain():
    """
    Returns the complete blockchain database of verified blocks.
    """
    return [block.to_dict() for block in blockchain.chain]

@app.get("/mempool")
def get_mempool():
    """
    Returns all pending transactions waiting to be mined.
    """
    return [tx.to_dict() for tx in blockchain.pending_transactions]

@app.get("/registry")
def get_registry():
    """
    Returns lists of all registered public key hashes.
    """
    return blockchain.registry

@app.post("/register")
def register_entity(data: RegisterEntity):
    """
    Registers the public key of a node, beacon, or validator authority.
    """
    if data.entity_type not in ["beacons", "nodes", "authorities"]:
        raise HTTPException(status_code=400, detail="Invalid entity type. Use 'beacons', 'nodes', or 'authorities'.")
        
    blockchain.registry[data.entity_type][data.entity_id] = data.public_key_pem
    return {"status": "success", "message": f"Registered {data.entity_id} as a {data.entity_type}."}

@app.post("/transaction")
def submit_transaction(data: SubmitTransactionModel):
    """
    Submits a Proof-of-Location record (transaction) into the mempool.
    """
    success, res = blockchain.submit_transaction(data.model_dump())
    if not success:
        raise HTTPException(status_code=400, detail=res)
    return {"status": "success", "tx_id": res}

@app.post("/quarantine/{tx_id}")
def quarantine_transaction(tx_id: str):
    global blockchain, quarantined_transactions
    found_tx = None
    for tx in blockchain.pending_transactions:
        if tx.tx_id == tx_id:
            found_tx = tx
            break
            
    if not found_tx:
        raise HTTPException(status_code=404, detail=f"Transaction {tx_id} not found in pending queue.")
        
    threat = "Consensus Violation"
    reason = "Failed consensus validation rules."
    
    # 1. Freshness Check
    current_time = int(time.time())
    if (current_time - found_tx.epoch_time) > 300:
        threat = "Beacon Replay Attack"
        reason = f"Freshness limit exceeded: attestation is {current_time - found_tx.epoch_time}s old (Max: 300s)."
    else:
        # 2. Fork Check
        conflicts = [tx for tx in blockchain.pending_transactions if tx.tx_id != found_tx.tx_id and tx.pkg_id == found_tx.pkg_id and tx.prev_proof_hash == found_tx.prev_proof_hash]
        if conflicts:
            threat = "Double-Location Fork Attack"
            reason = f"Conflicting fork path: multiple transactions branch from parent hash {found_tx.prev_proof_hash[:8]}..."
        else:
            # 3. Signature & Coordinate Forgery Checks
            node_key = blockchain.registry["nodes"].get(found_tx.node_id)
            beacon_key = blockchain.registry["beacons"].get(found_tx.beacon_id)
            if not node_key or not Validator.verify_node_signature(found_tx, node_key):
                threat = "Node Signature Tampering"
                reason = "Invalid node signature."
            elif not beacon_key or not Validator.verify_beacon_signature(found_tx, beacon_key):
                threat = "Location Coordinate Forgery"
                reason = "Invalid beacon signature."
                
    # Remove from pending pool
    blockchain.pending_transactions.remove(found_tx)
    
    quarantine_entry = {
        **found_tx.to_dict(),
        "quarantine_time": int(time.time()),
        "threat_type": threat,
        "reason": reason
    }
    quarantined_transactions.append(quarantine_entry)
    
    return {"status": "success", "message": f"Transaction {tx_id} quarantined successfully.", "quarantined": quarantine_entry}

@app.get("/quarantine")
def get_quarantine():
    global quarantined_transactions
    return quarantined_transactions

@app.post("/mine")
def mine_block(data: MineRequest):
    """
    Mines pending transactions into a block signed by an authorized validator.
    """
    if not blockchain.pending_transactions:
        raise HTTPException(status_code=400, detail="No pending transactions to mine.")

    # Use simulated authority key if none is provided
    if not data.authority_private_key_pem:
        if data.authority_id == "AUTHORITY-MAIN":
            p_key = auth_private_key
        elif data.authority_id in authority_keys:
            p_key = authority_keys[data.authority_id]
        else:
            raise HTTPException(status_code=400, detail=f"No key provided for authority '{data.authority_id}'")
    else:
        try:
            p_key = deserialize_private_key(data.authority_private_key_pem)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PEM private key format.")

    # Pass authority_keys dictionary to participate in consensus quorum signatures
    success, res = blockchain.mine_pending_transactions(data.authority_id, p_key, extra_keys=authority_keys)
    if not success:
        raise HTTPException(status_code=400, detail=res)
        
    return {
        "status": "success",
        "message": f"Block mined successfully and added to chain.",
        "block_hash": res
    }

@app.get("/package/history/{pkg_id}")
def query_package_history(pkg_id: str):
    """
    Traces and verifies the cryptographic chain of location records for a package.
    """
    history = blockchain.get_package_history(pkg_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No provenance history found for package '{pkg_id}'.")
        
    # Verify links mathematically in real-time
    verified_steps = []
    prev_hash = "0"
    
    for i, tx_dict in enumerate(history):
        tx = Transaction.from_dict(tx_dict)
        # Verify step linkages
        link_valid = (tx.prev_proof_hash == prev_hash)
        
        # Verify signatures
        beacon_key = blockchain.registry["beacons"].get(tx.beacon_id)
        node_key = blockchain.registry["nodes"].get(tx.node_id)
        
        sig_valid = False
        if beacon_key and node_key:
            sig_valid = (
                Validator.verify_beacon_signature(tx, beacon_key) and 
                Validator.verify_node_signature(tx, node_key)
            )
            
        verified_steps.append({
            "step_index": i,
            "tx_id": tx.tx_id,
            "pkg_id": tx.pkg_id,
            "node_id": tx.node_id,
            "beacon_id": tx.beacon_id,
            "location": tx.location,
            "epoch_time": tx.epoch_time,
            "prev_proof_hash": tx.prev_proof_hash,
            "link_valid": link_valid,
            "signatures_valid": sig_valid,
            "status": "VERIFIED" if (link_valid and sig_valid) else "FAILED"
        })
        
        prev_hash = tx.tx_id
        
    return {
        "pkg_id": pkg_id,
        "is_provenance_valid": all(step["status"] == "VERIFIED" for step in verified_steps),
        "steps_count": len(verified_steps),
        "history": verified_steps
    }

@app.get("/package/last_hash/{pkg_id}")
def query_package_last_hash(pkg_id: str):
    last_hash = blockchain.get_package_last_hash(pkg_id)
    return {"pkg_id": pkg_id, "last_hash": last_hash}

@app.post("/simulate/step")
def simulate_package_step(data: SimulateStepRequest):
    """
    Advances a package along one step of the selected route.
    Generates a valid Proof-of-Location and adds it to the mempool.
    """
    pkg_id = data.pkg_id
    route_name = data.route_name
    
    if route_name not in ROUTE_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid route name.")
        
    route_steps = ROUTE_TEMPLATES[route_name]
    
    # Check current simulation state
    if pkg_id not in simulated_packages or simulated_packages[pkg_id]["route_name"] != route_name:
        # Start at beginning of route
        current_index = 0
        simulated_packages[pkg_id] = {
            "route_name": route_name,
            "current_step_index": current_index
        }
    else:
        # Advance index
        current_index = simulated_packages[pkg_id]["current_step_index"] + 1
        if current_index >= len(route_steps):
            raise HTTPException(status_code=400, detail=f"Package {pkg_id} has already completed the route.")
        simulated_packages[pkg_id]["current_step_index"] = current_index

    target_step = route_steps[current_index].copy()
    if data.latitude is not None and data.longitude is not None:
        target_step["lat"] = data.latitude
        target_step["lon"] = data.longitude
        target_step["name"] = f"{target_step['name']} (Custom Pos: {data.latitude:.4f}, {data.longitude:.4f})"
    
    success, res = simulate_step(blockchain, beacons, nodes, pkg_id, target_step)
    if not success:
        # Revert step index change on failure
        if current_index == 0:
            del simulated_packages[pkg_id]
        else:
            simulated_packages[pkg_id]["current_step_index"] -= 1
        raise HTTPException(status_code=400, detail=res)
        
    return {
        "status": "success",
        "pkg_id": pkg_id,
        "location": target_step["name"],
        "step_index": current_index,
        "total_steps": len(route_steps),
        "tx_id": res,
        "completed": current_index == len(route_steps) - 1
    }

@app.post("/simulate/attack")
def simulate_attack(pkg_id: str, attack_type: str, route_name: str, step_index: int = 1,
                    replay_delay: int = 7200, fork_node_id: str = "NODE-304",
                    spoof_lat: float = 40.7128, spoof_lon: float = -74.0060):
    """
    Creates and injects a simulated security attack into the ledger.
    Shows the red team mechanisms working.
    """
    if route_name not in ROUTE_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid route name.")
    
    route_steps = ROUTE_TEMPLATES[route_name]
    if step_index < 0 or step_index >= len(route_steps):
        raise HTTPException(status_code=400, detail="Invalid step index.")
        
    target_step = route_steps[step_index]
    step_id = target_step["id"]
    beacon_id = f"BEACON-{step_id}"
    node_id = f"NODE-{step_id}"
    
    beacon: LocalAttestationBeacon = beacons.get(beacon_id)
    node: LogisticsGateway = nodes.get(node_id)
    
    if not beacon or not node:
        raise HTTPException(status_code=404, detail="Simulator Beacons/Nodes not initialized.")

    # Dynamically register primary attack target keys if not present
    if beacon_id not in blockchain.registry["beacons"]:
        blockchain.add_beacon(beacon_id, beacon.get_public_key_pem())
    if node_id not in blockchain.registry["nodes"]:
        blockchain.add_node(node_id, node.get_public_key_pem())

    # 1. REPLAY ATTACK
    if attack_type == "replay":
        # Create an attestation token from the past using parameterized delay
        expired_time = int(time.time()) - replay_delay
        expired_token = beacon.generate_attestation_token(custom_time=expired_time)
        
        # Build transaction using the expired beacon token
        prev_hash = blockchain.get_package_last_hash(pkg_id)
        tx_dict = node.create_proof_of_location(
            pkg_id=pkg_id,
            beacon_token=expired_token,
            prev_proof_hash=prev_hash
        )
        
        # Manually alter the transaction submit timestamp to bypass immediate API filters if any
        # But keeping the epoch_time inside block as expired
        success, res = blockchain.submit_transaction(tx_dict)
        if not success:
            raise HTTPException(status_code=400, detail=f"Attack failed early during mempool check: {res}")
            
        # Replays bypass mempool check if keys are valid, but must fail during mining check or chain query
        return {"status": "injected", "detail": f"Replayed beacon transaction (age: {replay_delay}s) added to mempool. Run /mine to verify rejection.", "tx_id": res}

    # 2. FORK / DOUBLE-LOCATION ATTACK
    elif attack_type == "fork":
        # Submit two location proofs with same prev_proof_hash but different locations
        prev_hash = blockchain.get_package_last_hash(pkg_id)
        
        # Target A: Actual step location
        token_a = beacon.generate_attestation_token()
        tx_a = node.create_proof_of_location(pkg_id=pkg_id, beacon_token=token_a, prev_proof_hash=prev_hash)
        
        # Target B: Counterfeit location (using custom parameterized node_b_id)
        node_b_id = fork_node_id
        beacon_b_id = fork_node_id.replace("NODE", "BEACON")
        
        # Check if custom node_b_id node and beacon are initialized
        node_b: LogisticsGateway = nodes.get(node_b_id)
        beacon_b: LocalAttestationBeacon = beacons.get(beacon_b_id)
        
        if not node_b or not beacon_b:
            # Dynamically initialize if custom drawing node is chosen
            beacon_b = LocalAttestationBeacon(beacon_b_id, 12.9716, 77.5946)
            node_b = LogisticsGateway(node_b_id)
            beacons[beacon_b_id] = beacon_b
            nodes[node_b_id] = node_b
            
        if beacon_b_id not in blockchain.registry["beacons"]:
            blockchain.add_beacon(beacon_b_id, beacon_b.get_public_key_pem())
        if node_b_id not in blockchain.registry["nodes"]:
            blockchain.add_node(node_b_id, node_b.get_public_key_pem())
            
        token_b = beacon_b.generate_attestation_token()
        tx_b = node_b.create_proof_of_location(pkg_id=pkg_id, beacon_token=token_b, prev_proof_hash=prev_hash)
        
        # Submit both transactions to mempool (signatures are correct, they both reference same parent)
        s1, r1 = blockchain.submit_transaction(tx_a)
        s2, r2 = blockchain.submit_transaction(tx_b)
        
        return {
            "status": "injected",
            "detail": "Fork transactions submitted to mempool. Run /mine to see consensus validator reject the block.",
            "txs": [r1, r2]
        }

    # 3. INVALID SIGNATURE ATTACK
    elif attack_type == "invalid_signature":
        prev_hash = blockchain.get_package_last_hash(pkg_id)
        token = beacon.generate_attestation_token()
        tx_dict = node.create_proof_of_location(pkg_id=pkg_id, beacon_token=token, prev_proof_hash=prev_hash)
        
        # Tamper with the Node Signature by replacing characters
        tx_dict["node_sig"] = tx_dict["node_sig"][:-4] + "abcd"
        
        success, res = blockchain.submit_transaction(tx_dict)
        if not success:
            return {"status": "blocked", "detail": f"Attack successfully blocked by API mempool validation: {res}"}
            
        raise HTTPException(status_code=500, detail="Mempool validation failed to catch tampered signature!")

    # 4. LOCATION FORGERY ATTACK
    elif attack_type == "gps_forgery":
        # The node attempts to submit coordinates (custom parameterized spoof_lat/lon)
        # signs it with the Shenzhen beacon ID, or alters coordinates in the transaction AFTER the beacon signs them.
        prev_hash = blockchain.get_package_last_hash(pkg_id)
        token = beacon.generate_attestation_token()
        
        # Corrupt the coordinates in the beacon token payload before passing to the node
        fake_token = token.copy()
        fake_token["location"] = {"lat": spoof_lat, "lon": spoof_lon}
        
        tx_dict = node.create_proof_of_location(pkg_id=pkg_id, beacon_token=fake_token, prev_proof_hash=prev_hash)
        
        success, res = blockchain.submit_transaction(tx_dict)
        if not success:
            return {"status": "blocked", "detail": f"Attack successfully blocked. Beacon signature verification failed due to coordinate modification: {res}"}
            
        raise HTTPException(status_code=500, detail="Mempool validation failed to catch forged coordinates!")

    else:
        raise HTTPException(status_code=400, detail="Invalid attack type.")

from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="web", html=True), name="web")
