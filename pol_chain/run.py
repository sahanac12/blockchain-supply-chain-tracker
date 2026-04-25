import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pol_chain.simulation.simulate import SupplyChainSimulator, save_chain
from pol_chain.chain.blockchain import Blockchain

def main():
    print("=" * 60)
    print("🚀 Booting PoL Chain System...")
    print("=" * 60)
    
    chain_path = os.path.join(os.path.dirname(__file__), 'data', 'chain.json')
    if not os.path.exists(chain_path):
        print("[*] Pre-populating blockchain with normal journey...")
        sim = SupplyChainSimulator()
        bc = sim.simulate_journey(inject_attack=False)
        save_chain(bc, chain_path)
        print("[*] Chain saved to data/chain.json")
    else:
        print("[*] Found existing chain.json. Using saved state.")
        
    print("\n" + "=" * 60)
    print("🌐 Starting API Server on http://localhost:5000")
    print("📊 Dashboard is available at: file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), 'dashboard', 'index.html')).replace('\\', '/'))
    print("=" * 60 + "\n")
    
    server_path = os.path.join(os.path.dirname(__file__), 'api', 'server.py')
    
    try:
        # Launch server
        subprocess.run([sys.executable, server_path])
    except KeyboardInterrupt:
        print("\nShutting down PoL Chain System.")

if __name__ == "__main__":
    main()
