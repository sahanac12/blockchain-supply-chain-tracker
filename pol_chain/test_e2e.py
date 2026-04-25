import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pol_chain.simulation.simulate import SupplyChainSimulator, save_chain, load_chain

def main():
    print("Running Final E2E Test...")
    sim = SupplyChainSimulator()
    bc = sim.simulate_journey(inject_attack=False)
    
    chain_path = os.path.join(os.path.dirname(__file__), 'data', 'test_chain.json')
    save_chain(bc, chain_path)
    
    loaded_bc = load_chain(chain_path)
    is_valid, issues = loaded_bc.verify_chain()
    
    if is_valid:
        print("All systems nominal — PoL Chain ready")
    else:
        print("E2E failed:", issues)

if __name__ == "__main__":
    main()
