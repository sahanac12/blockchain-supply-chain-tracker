# Decentralized Proof-of-Location (POL) Supply Chain Tracker

A security-focused, decentralized location-attestation ledger designed to secure global supply chain provenance. This project leverages **ECDSA cryptography**, bottom-up **Merkle Trees**, and a **Proof-of-Authority (PoA)** consensus quorum to guarantee immutable, coordinate-forgery-proof physical tracking records.

---

## Core Features

- **Double-Signature Attestation**: Leverages a dual-signature scheme where local Location Beacons (representing physical locations) and Logistics Gateway Nodes (scanning nodes) must sign attestations.
- **Proof-of-Authority Consensus**: Blocks are validated and appended to the ledger via a quorum of authorized validator nodes, securing the network from state manipulation.
- **Merkle Tree Proofs**: Implements bottom-up Merkle Tree construction for verified transactions in each block, allowing lightweight clients to verify transaction membership using sibling path proofs.
- **Red Team Security Sandbox**: Simulates and defends against four critical attack vectors:
  - **Replay Attacks** (caught by a 300-second temporal freshness constraint)
  - **GPS Coordinate Forgery** (caught by validating the beacon signature against coordinates)
  - **Double-Location Fork Attacks** (caught by state tracking verification)
  - **Signature Tampering** (caught by public key verification)
- **Interactive Dashboards**: Features a static Web Console built with HTML/JS and a premium Streamlit dashboard with HSL dark-mode styling and live geographical maps.

---

## Project Structure

```text
├── app/                  # FastAPI Application
│   └── main.py           # REST API & static file serving configuration
├── blockchain/           # Core Blockchain implementation
│   ├── block.py          # Block and Transaction data structures
│   ├── chain.py          # Ledger state management and transaction mempool
│   └── validator.py      # Block, transaction, and signature validation logic
├── crypto/               # Cryptographic utilities
│   ├── hashing.py        # SHA-256 helpers and Merkle Tree logic
│   ├── keys.py           # PEM Key serialization and deserialization
│   └── signatures.py     # ECDSA signature generation and verification
├── dashboard/            # Streamlit visualization panel
│   └── app.py            # Glassmorphic multi-page auditor console
├── node/                 # Physical system simulations
│   ├── beacon.py         # Local Attestation Beacon simulation (LAT generation)
│   ├── gateway.py        # Logistics Gateway Node simulation (Dual signature signing)
│   └── generator.py      # Predefined route paths in Bangalore
├── tests/                # Automated unit tests
│   ├── test_attacks.py   # Red-team vector test cases
│   └── test_happy_path.py# Normal transaction flow tests
├── web/                  # Static Web Console assets
│   ├── index.html        # Web Console landing page
│   ├── app.js            # Frontend API client logic
│   └── style.css         # Styling stylesheets
├── requirements.txt      # Python dependencies
├── run.bat               # Windows execution batch file
└── docker-compose.yml    # Docker services config
```

---

## Setup and Installation

### Prerequisites
- Python 3.10+ installed on your system.

### Installation
1. Clone this repository to your local workspace.
2. Open your terminal in the workspace directory and install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Project

### Option 1: Native Execution (Recommended)
You can run the application servers natively in separate terminals:

1. **Start the FastAPI Backend**:
   This hosts the REST API endpoints and serves the static Web Console:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   *You can visit the static Web Console at **[http://127.0.0.1:8000](http://127.0.0.1:8000)***.

2. **Start the Streamlit Auditor Dashboard**:
   ```bash
   streamlit run dashboard/app.py
   ```
   *You can interact with the Dashboard at **[http://localhost:8501](http://localhost:8501)***.

### Option 2: Windows Batch Launcher
If you are on Windows, you can double-click or run the console launcher to start the backend and open the browser automatically:
```cmd
run.bat
```

### Option 3: Docker Compose
Build and run the entire stack (FastAPI Backend + Streamlit Dashboard) inside Docker containers:
```bash
docker-compose up --build
```
- Web Console: [http://localhost:8000](http://localhost:8000)
- Streamlit Dashboard: [http://localhost:8501](http://localhost:8501)

---

## Running Unit Tests

To run the security testing suites and verify the cryptographic integrity of the ledger:
```bash
pytest -v
```

This will run all test suites covering key generation, Merkle path verification, consensus logic, quarantine mechanics, and the four security attack vectors.
