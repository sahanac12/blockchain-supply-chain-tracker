import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pol_chain.nodes.node import Node
from pol_chain.chain.blockchain import Blockchain
from pol_chain.chain.block import PolBlock
from pol_chain.utils.crypto import sign_data
from pol_chain.utils.geo import is_plausible

class SupplyChainSimulator:
    def __init__(self):
        self.nodes = []
        self.load_nodes()
        self.package_id = "PKG-2024-PHARMA-001"
        
    def load_nodes(self):
        nodes_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'nodes.json')
        with open(nodes_file, 'r') as f:
            data = json.load(f)
            
        for d in data:
            self.nodes.append(Node(
                name=d["name"],
                location_name=d["location_name"],
                lat=d["lat"],
                lon=d["lon"]
            ))
            
    def generate_wifi_fingerprint(self, location_name: str):
        fingerprints = {
            "Chennai, India": [
                {"bssid": "00:11:22:33:44:55", "rssi": -45, "ssid": "Factory_WIFI_1"},
                {"bssid": "00:11:22:33:44:56", "rssi": -60, "ssid": "Factory_WIFI_2"},
                {"bssid": "00:11:22:33:44:57", "rssi": -72, "ssid": "Factory_Guest"}
            ],
            "On NH48 highway": [
                {"bssid": "aa:bb:cc:dd:ee:11", "rssi": -85, "ssid": "Toll_Plaza_Free"},
                {"bssid": "aa:bb:cc:dd:ee:22", "rssi": -90, "ssid": "Dhaba_Net"},
                {"bssid": "aa:bb:cc:dd:ee:33", "rssi": -70, "ssid": "Truck_Hotspot"}
            ],
            "Bengaluru, India": [
                {"bssid": "11:22:33:44:55:66", "rssi": -50, "ssid": "WH_Corp_Network"},
                {"bssid": "11:22:33:44:55:77", "rssi": -55, "ssid": "WH_IoT"},
                {"bssid": "11:22:33:44:55:88", "rssi": -80, "ssid": "Blr_City_Wifi"}
            ],
            "Hosur, India": [
                {"bssid": "ff:ee:dd:cc:bb:aa", "rssi": -40, "ssid": "Retail_POS"},
                {"bssid": "ff:ee:dd:cc:bb:ab", "rssi": -65, "ssid": "Retail_Guest"},
                {"bssid": "ff:ee:dd:cc:bb:ac", "rssi": -75, "ssid": "Mall_Wifi_Free"}
            ]
        }
        return fingerprints.get(location_name, [
            {"bssid": "00:00:00:00:00:00", "rssi": -99, "ssid": "Unknown"}
        ])

    def simulate_journey(self, inject_attack=False) -> Blockchain:
        bc = Blockchain()
        genesis = bc.genesis_block()
        bc.chain.append(genesis)
        
        current_time = datetime.fromisoformat("2024-01-15T06:00:00+00:00")
        travel_times = [0, 2, 5, 2] # hours delay per node step
        
        for i, node in enumerate(self.nodes):
            current_time += timedelta(hours=travel_times[i])
            curr_lat = node.lat
            curr_lon = node.lon
            timestamp_str = current_time.isoformat().replace('+00:00', 'Z')
            
            if inject_attack and i == 2:
                curr_lat = 51.5074 # London
                curr_lon = -0.1278
                # Teleport block timestamp to only 3 mins after previous block
                prev_ts = datetime.fromisoformat(bc.chain[-1].timestamp.replace('Z', '+00:00'))
                current_time = prev_ts + timedelta(minutes=3)
                timestamp_str = current_time.isoformat().replace('+00:00', 'Z')
                
            prev_block = bc.chain[-1]
            
            flagged = False
            flag_reason = ""
            if prev_block.block_index > 0:
                is_plaus, reason = is_plausible(
                    prev_lat=prev_block.lat,
                    prev_lon=prev_block.lon,
                    prev_timestamp=prev_block.timestamp,
                    curr_lat=curr_lat,
                    curr_lon=curr_lon,
                    curr_timestamp=timestamp_str,
                    transport="truck"
                )
                if not is_plaus:
                    flagged = True
                    flag_reason = reason

            b = PolBlock(
                block_index=i+1,
                package_id=self.package_id,
                node_id=node.node_id,
                node_name=node.name,
                timestamp=timestamp_str,
                lat=curr_lat,
                lon=curr_lon,
                wifi_fingerprint=self.generate_wifi_fingerprint(node.location_name),
                prev_hash=prev_block.block_hash,
                flagged=flagged,
                flag_reason=flag_reason
            )
            
            b.claim_hash = b.compute_claim_hash()
            b.signature = sign_data(node.private_key_pem, {"claim_hash": b.claim_hash})
            b.block_hash = b.compute_block_hash()
            
            bc.add_block(b)
            
        return bc

    def tamper_and_detect(self, bc: Blockchain):
        # Mutate block 1's lat by +0.5
        bc.chain[1].lat += 0.5
        
        # Verify
        is_valid, issues = bc.verify_chain()
        return is_valid, issues

def print_chain_summary(bc: Blockchain, title: str):
    print(f"\n--- {title} ---")
    print(f"{'Block#':<7} | {'Node':<13} | {'Timestamp':<20} | {'Coords':<20} | {'Flagged':<7} | {'Hash':<8}")
    print("-" * 88)
    for b in bc.chain:
        coords = f"{b.lat:.4f}, {b.lon:.4f}"
        flag_str = "Yes" if b.flagged else "No"
        print(f"{b.block_index:<7} | {b.node_name:<13} | {b.timestamp:<20} | {coords:<20} | {flag_str:<7} | {b.block_hash[:8]}")
        if b.flagged:
            print(f"  -> Flag Reason: {b.flag_reason}")

def main():
    sim = SupplyChainSimulator()
    
    # 1. Normal Simulation
    normal_chain = sim.simulate_journey(inject_attack=False)
    print_chain_summary(normal_chain, "NORMAL JOURNEY")
    
    # 2. Attack Simulation
    attack_chain = sim.simulate_journey(inject_attack=True)
    print_chain_summary(attack_chain, "ATTACK JOURNEY (Teleportation)")
    
    # 3. Tamper and Detect
    print("\n--- TAMPER & DETECT ---")
    print("Tampering with Normal Journey's Block 1 (modifying latitude +0.5)...")
    is_valid, issues = sim.tamper_and_detect(normal_chain)
    
    if not is_valid:
        print("Tampering SUCCESSFULLY caught!")
        for issue in issues:
            print(f" - {issue}")
    else:
        print("Tampering FAILED to be caught! (This is a bug)")

if __name__ == "__main__":
    main()

def save_chain(chain: Blockchain, path: str):
    with open(path, 'w') as f:
        json.dump(chain.to_dict(), f, indent=2)

def load_chain(path: str) -> Blockchain:
    with open(path, 'r') as f:
        d = json.load(f)
    return Blockchain.from_dict(d)
