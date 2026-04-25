# PoL Chain (Proof of Location)

PoL Chain is a Supply Chain Anti-Counterfeiting demonstration that uses cryptographic hashing and spatial plausibility heuristics to ensure package journeys cannot be forged or teleported. It verifies each step of a shipment via deterministic hashing, RSA signatures, and Wi-Fi fingerprinting.

## Architecture

```text
[Node (Factory/Truck)] 
        ↓
signs PoL Claim (Coords, Hash, Timestamp)
        ↓
    [PolBlock] 
        ↓
    chains to 
        ↓
  [Blockchain]
        ↓
    [API Server]
        ↓
   [Dashboard UI]
```

## Setup Instructions

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the system:
   ```bash
   python run.py
   ```
   *This automatically simulates a genesis journey, saves it to `data/chain.json`, and boots the Flask API.*

3. Open the Dashboard:
   Double-click `dashboard/index.html` in your browser.

## API Endpoint Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server health check |
| GET | `/api/chain` | Full blockchain JSON & validation status |
| GET | `/api/chain/verify` | Runs full cryptographic validation of hashes and linkages |
| GET | `/api/package/<id>` | Blocks related to a specific package ID |
| POST | `/api/simulate` | Generates a fresh simulation (accepts `{"inject_attack": bool}`) |
| POST | `/api/tamper` | Modifies block data in memory to demonstrate the blockchain catching tampering |
| GET | `/api/nodes` | Public identity details of the 4 participant nodes |

## Attack Detection

The PoL Chain secures against counterfeit tracking data using two core methods:
1. **Hash Chain Verification**: Every block's hash includes the `prev_hash` and the cryptographically signed `claim_hash`. If an attacker alters coordinates on an existing block, the signature and block hash become invalid.
2. **Spatial Plausibility**: When evaluating consecutive blocks, the system calculates the time elapsed and physical distance (via Haversine formula). If the implied speed exceeds realistic transport limits (e.g. >200 km/h for ground), the system explicitly flags the leg as a forgery/teleportation attack.

## Simulations

- **Normal Journey**: Generates a valid timeline from Factory to Retail Store.
- **Attack Journey**: Triggers a teleportation by injecting a Warehouse log in London with an impossible timestamp (only 3 minutes after the Truck ping in India).
