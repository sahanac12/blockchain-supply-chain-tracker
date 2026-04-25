import json
import os
import sys

# Add the parent directory to the path so we can import pol_chain
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pol_chain.nodes.node import Node
from pol_chain.utils.crypto import sign_data, verify_signature

def main():
    # Load nodes from json
    nodes_file = os.path.join(os.path.dirname(__file__), 'data', 'nodes.json')
    with open(nodes_file, 'r') as f:
        nodes_data = json.load(f)
        
    nodes = []
    for n in nodes_data:
        node = Node(name=n['name'], location_name=n['location_name'], lat=n['lat'], lon=n['lon'])
        nodes.append(node)
        print(f"Created node: {node.name} ({node.node_id})")
        
    node1 = nodes[0]
    
    test_dict = {"message": "Test Message", "value": 42}
    print(f"\nSigning data with Node 1 ({node1.name})...")
    
    signature = sign_data(node1.private_key_pem, test_dict)
    print(f"Signature generated: {signature[:30]}...")
    
    print("\nVerifying signature with Node 1's public key...")
    is_valid = verify_signature(node1.public_key_pem, test_dict, signature)
    
    if is_valid:
        print("PASS")
    else:
        print("FAIL")

if __name__ == "__main__":
    main()
