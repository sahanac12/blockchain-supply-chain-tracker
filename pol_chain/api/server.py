import os
import sys
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pol_chain.simulation.simulate import SupplyChainSimulator
from pol_chain.utils.geo import haversine_km

app = Flask(__name__)
CORS(app)

# Global simulator and blockchain state
simulator = SupplyChainSimulator()
CHAIN_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'chain.json')
from pol_chain.simulation.simulate import save_chain, load_chain

if os.path.exists(CHAIN_PATH):
    global_chain = load_chain(CHAIN_PATH)
else:
    global_chain = simulator.simulate_journey(inject_attack=False)
    save_chain(global_chain, CHAIN_PATH)

@app.route('/')
def serve_index():
    dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'index.html'))
    if os.path.exists(dashboard_path):
        return send_file(dashboard_path)
    return jsonify({"message": "PoL Chain API is running."})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/chain', methods=['GET'])
def get_chain():
    is_valid, issues = global_chain.verify_chain()
    return jsonify({
        "chain": [b.to_dict() for b in global_chain.chain],
        "is_valid": is_valid,
        "integrity_issues": issues
    })

@app.route('/api/chain/verify', methods=['GET'])
def verify_chain_endpoint():
    is_valid, issues = global_chain.verify_chain()
    return jsonify({
        "valid": is_valid,
        "issues": issues
    })

@app.route('/api/package/<package_id>', methods=['GET'])
def get_package(package_id):
    blocks = [b for b in global_chain.chain if b.package_id == package_id]
    
    total_distance_km = 0.0
    flagged_blocks = 0
    
    # Calculate summary based on chronological blocks
    for i in range(1, len(blocks)):
        prev_b = blocks[i-1]
        curr_b = blocks[i]
        total_distance_km += haversine_km(prev_b.lat, prev_b.lon, curr_b.lat, curr_b.lon)
        if curr_b.flagged:
            flagged_blocks += 1
            
    # Include genesis flagged if any (shouldn't be, but just in case)
    if len(blocks) > 0 and blocks[0].flagged:
        flagged_blocks += 1

    return jsonify({
        "package_id": package_id,
        "blocks": [b.to_dict() for b in blocks],
        "journey_summary": {
            "total_distance_km": round(total_distance_km, 2),
            "flagged_blocks": flagged_blocks
        }
    })

@app.route('/api/simulate', methods=['POST'])
def run_simulation():
    global global_chain
    data = request.json or {}
    inject_attack = data.get("inject_attack", False)
    
    global_chain = simulator.simulate_journey(inject_attack=inject_attack)
    return jsonify({
        "message": "Simulation executed successfully",
        "chain": [b.to_dict() for b in global_chain.chain]
    })

@app.route('/api/tamper', methods=['POST'])
def tamper_block():
    global global_chain
    data = request.json or {}
    block_index = data.get("block_index")
    new_lat = data.get("new_lat")
    
    if block_index is None or new_lat is None:
        return jsonify({"error": "block_index and new_lat are required"}), 400
        
    if not isinstance(block_index, int) or block_index < 0 or block_index >= len(global_chain.chain):
        return jsonify({"error": f"block_index {block_index} is out of range"}), 400
        
    # Mutate the block
    global_chain.chain[block_index].lat = new_lat
    
    # Verify the chain after tampering
    is_valid, issues = global_chain.verify_chain()
    
    return jsonify({
        "message": f"Block {block_index} tampered successfully",
        "valid": is_valid,
        "issues": issues
    })

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    return jsonify({
        "nodes": [n.to_public_dict() for n in simulator.nodes]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
