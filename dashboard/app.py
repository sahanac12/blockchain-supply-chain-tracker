import streamlit as st
import requests
import pandas as pd
import json
import time

# Set page configuration with a premium dark theme feel
st.set_page_config(
    page_title="POL Supply Chain Provenance",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL
API_URL = "http://localhost:8000"

# Inject Custom CSS for Premium Dark Glassmorphism Aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Mono&display=swap');
    
    /* Apply base styling */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background-color: #080B11;
        color: #E2E8F0;
    }
    
    /* Header styling */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Glassmorphic card styling */
    .glass-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 20px;
    }
    
    .glass-card-header {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 12px;
        color: #F8FAFC;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding-bottom: 8px;
    }
    
    /* Monospace text for logs and hashes */
    .mono-text {
        font-family: 'Space Mono', monospace;
        font-size: 0.85rem;
        background: rgba(0, 0, 0, 0.4);
        padding: 4px 8px;
        border-radius: 6px;
        color: #A78BFA;
    }
    
    /* Custom status tags */
    .status-badge-verified {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .status-badge-failed {
        background-color: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .status-badge-pending {
        background-color: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to query backend
def get_api_data(endpoint: str):
    try:
        response = requests.get(f"{API_URL}{endpoint}")
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.ConnectionError:
        return None

def get_package_combined_history(pkg_id: str):
    # 1. Fetch confirmed history
    confirmed = []
    hist_res = requests.get(f"{API_URL}/package/history/{pkg_id}")
    if hist_res.status_code == 200:
        confirmed = hist_res.json().get("history", [])
        
    # 2. Fetch mempool
    mempool_txs = get_api_data("/mempool")
    mempool_steps = []
    if mempool_txs:
        # Find transactions for this package in mempool
        pkg_mempool = [tx for tx in mempool_txs if tx["pkg_id"] == pkg_id]
        pkg_mempool.sort(key=lambda x: x["epoch_time"])
        
        start_index = len(confirmed)
        for i, tx in enumerate(pkg_mempool):
            mempool_steps.append({
                "step_index": start_index + i,
                "tx_id": tx["tx_id"],
                "pkg_id": tx["pkg_id"],
                "node_id": tx["node_id"],
                "beacon_id": tx["beacon_id"],
                "location": tx["location"],
                "epoch_time": tx["epoch_time"],
                "prev_proof_hash": tx["prev_proof_hash"],
                "link_valid": True,
                "signatures_valid": True,
                "status": "PENDING_MINING"
            })
            
    return confirmed + mempool_steps

# Sidebar Setup
st.sidebar.markdown("<h2 style='text-align: center;'>POL Protocol</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; color: #94A3B8; font-size: 0.9rem;'>POL Console</p>", unsafe_allow_html=True)

# Check API health
health_data = get_api_data("/status")
if health_data is None:
    st.sidebar.error("Backend Server Offline")
    st.sidebar.info("Run: `uvicorn app.main:app --reload` to start the API backend.")
    st.error("### API Backend Connection Lost\nPlease ensure the FastAPI server is running on `http://localhost:8000` to interact with the project.")
    st.stop()
else:
    st.sidebar.success("Backend Connected")

# Show Quick Stats in Sidebar
st.sidebar.markdown("### Ledger Quick Stats")
st.sidebar.markdown(f"**Verified Blocks:** `{health_data['blocks_count']}`")
st.sidebar.markdown(f"**Mempool Pool:** `{health_data['pending_transactions_count']}`")
st.sidebar.markdown(f"**Location Beacons:** `{health_data['registered_beacons']}`")
st.sidebar.markdown(f"**Logistics Nodes:** `{health_data['registered_nodes']}`")

# Navigation Menu
navigation = st.sidebar.radio(
    "Navigation Node",
    ["Supply Chain Simulation", "Provenance Auditor", "Block Explorer", "Security Attack Panel"]
)

# Render Pages based on Navigation
if navigation == "Supply Chain Simulation":
    st.markdown("## Supply Chain Route Simulation")
    st.markdown("Simulate package movements along pre-defined cargo routes. Each step generates a physical location scan backed by cryptographic attestation.")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Generate New Shipment")
        
        # Form to start package
        route_name = st.selectbox(
            "Select Logistics Route",
            ["standard_delivery", "electronics_import", "pharmaceuticals_cold_chain"],
            format_func=lambda x: "Warehouse ──► Delivery Truck ──► Retail Store" if x == "standard_delivery" else "Electronics Import Path (Shenzhen -> NYC)" if x == "electronics_import" else "Pharma Cold Chain (Munich -> Miami)"
        )
        
        pkg_id = st.text_input("Enter Package Serial / ID", value="PKG-EL-209", max_chars=15)
        
        if st.button("Initialize & Scan Package", use_container_width=True):
            # Fire API call to simulate step
            res = requests.post(f"{API_URL}/simulate/step", json={"pkg_id": pkg_id, "route_name": route_name})
            if res.status_code == 200:
                data = res.json()
                st.success(f"Initialized! Scanned at: {data['location']}")
            else:
                st.error(res.json().get("detail", "Error starting package."))
        
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Move Package Forward")
        
        # Query chain to find packages in progress
        blocks = get_api_data("/chain")
        active_pkgs = set()
        if blocks:
            for b in blocks:
                for tx in b["transactions"]:
                    active_pkgs.add(tx["pkg_id"])
                    
        # Check mempool packages too
        mempool = get_api_data("/mempool")
        if mempool:
            for tx in mempool:
                active_pkgs.add(tx["pkg_id"])

        if active_pkgs:
            selected_pkg = st.selectbox("Select Active Package in Transit", sorted(list(active_pkgs)))
            # Quick check route for this package
            pkg_history_res = requests.get(f"{API_URL}/package/history/{selected_pkg}")
            
            # Suggest matching route
            if pkg_history_res.status_code == 200:
                history_data = pkg_history_res.json()
                # Determine which route based on node IDs in history
                first_node = history_data["history"][0]["node_id"]
                if "SHENZHEN" in first_node:
                    inferred_route = "electronics_import"
                elif "WHSE" in first_node:
                    inferred_route = "standard_delivery"
                else:
                    inferred_route = "pharmaceuticals_cold_chain"
            else:
                inferred_route = "standard_delivery"

            if st.button("Register Next Location Scan", use_container_width=True):
                res = requests.post(f"{API_URL}/simulate/step", json={"pkg_id": selected_pkg, "route_name": inferred_route})
                if res.status_code == 200:
                    data = res.json()
                    st.success(f"Advanced! Scanned at {data['location']}.")
                    if data["completed"]:
                        st.balloons()
                        st.info("Route completed! Package has safely arrived at destination retail node.")
                else:
                    st.error(res.json().get("detail", "Error advancement. Has it completed its route?"))
        else:
            st.warning("No active packages. Please initialize a shipment first.")
            
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Live Package Routing Coordinates")
        
        if active_pkgs:
            # Draw the Route Stepper for the currently selected package if one is in transit
            if 'selected_pkg' in locals() and selected_pkg:
                st.markdown(f"**Selected Package Path:** `{selected_pkg}` ({inferred_route.replace('_', ' ').title()})")
                
                # Fetch combined history of this package
                combined_history = get_package_combined_history(selected_pkg)
                history_nodes = {step["node_id"]: step for step in combined_history}
                
                # Get route steps
                from node.generator import ROUTE_TEMPLATES
                route_steps = ROUTE_TEMPLATES[inferred_route]
                
                # Build custom HTML Stepper
                stepper_html = '<div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(0, 0, 0, 0.2); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 20px; overflow-x: auto;">'
                
                for i, step in enumerate(route_steps):
                    step_node_id = f"NODE-{step['id']}"
                    step_name = step["name"]
                    
                    # Determine icon based on step ID
                    icon = ""
                    if "TRUCK" in step_node_id:
                        icon = ""
                    elif "RETAIL" in step_node_id or "STORE" in step_node_id or "PHARMA" in step_node_id:
                        icon = ""
                    elif "PORT" in step_node_id or "AIR" in step_node_id:
                        icon = ""
                    
                    step_history = history_nodes.get(step_node_id)
                    
                    if step_history:
                        if step_history.get("status") == "PENDING_MINING":
                            circle_bg = "#F59E0B"
                            shadow = "rgba(245, 158, 11, 0.3)"
                            status_label = "In Mempool"
                            label_color = "#FBBF24"
                        else:
                            circle_bg = "#10B981"
                            shadow = "rgba(16, 185, 129, 0.3)"
                            status_label = "Confirmed"
                            label_color = "#34D399"
                    else:
                        circle_bg = "rgba(255, 255, 255, 0.05)"
                        shadow = "rgba(0, 0, 0, 0)"
                        status_label = "Not Reached"
                        label_color = "#64748B"
                    
                    stepper_html += f"""
                    <div style="text-align: center; min-width: 80px; flex: 1; margin: 0 5px;">
                        <div style="width: 36px; height: 36px; border-radius: 50%; background: {circle_bg}; color: white; display: flex; align-items: center; justify-content: center; margin: 0 auto 6px; font-size: 1.1rem; box-shadow: 0 0 10px {shadow}; transition: all 0.3s ease;">
                            {icon}
                        </div>
                        <div style="font-weight: 600; color: #F8FAFC; font-size: 0.75rem; line-height: 1.1;">{step_name}</div>
                        <div style="font-size: 0.65rem; color: {label_color}; font-weight: 600; margin-top: 2px;">{status_label}</div>
                    </div>
                    """
                    
                    if i < len(route_steps) - 1:
                        next_node_id = f"NODE-{route_steps[i+1]['id']}"
                        next_reached = next_node_id in history_nodes
                        line_color = circle_bg if (step_history and next_reached) else "rgba(255, 255, 255, 0.05)"
                        stepper_html += f'<div style="flex: 1; height: 2px; background: {line_color}; min-width: 20px; margin-bottom: 24px;"></div>'
                        
                stepper_html += '</div>'
                st.markdown(stepper_html, unsafe_allow_html=True)

            # Gather tracking data for all active packages
            locations_df = []
            for pkg in active_pkgs:
                combined_history = get_package_combined_history(pkg)
                for step in combined_history:
                    status_text = "Confirmed" if step.get("status") != "PENDING_MINING" else "Pending Mining"
                    locations_df.append({
                        "Package ID": pkg,
                        "Location Node": step["node_id"],
                        "lat": step["location"]["lat"],
                        "lon": step["location"]["lon"],
                        "Time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(step["epoch_time"])),
                        "Status": status_text
                    })
            
            if locations_df:
                df = pd.DataFrame(locations_df)
                st.dataframe(df, use_container_width=True)
                st.map(df, size=15)
            else:
                st.info("No location scans available. Advance a package on its route to display coordinates.")
        else:
            st.info("Map is empty. Initialize a package to view real-time location routing.")
            
        st.markdown('</div>', unsafe_allow_html=True)

elif navigation == "Provenance Auditor":
    st.markdown("## Provenance Chain Inspector")
    st.markdown("Scan or type a package serial identifier to verify its cryptographic chain of custody. The auditor verifies hash links and public key signatures at every node step.")

    # Retrieve all packages
    blocks = get_api_data("/chain")
    pkg_list = set()
    if blocks:
        for b in blocks:
            for tx in b["transactions"]:
                pkg_list.add(tx["pkg_id"])

    search_pkg = st.text_input("Scan RFID / Enter Package ID", value=list(pkg_list)[0] if pkg_list else "PKG-EL-209")

    if st.button("Query Cryptographic Audit Trail"):
        res = requests.get(f"{API_URL}/package/history/{search_pkg}")
        if res.status_code == 200:
            audit = res.json()
            
            # Overall status card
            if audit["is_provenance_valid"]:
                st.markdown('<div class="status-badge-verified">PROVENANCE VERIFIED: Unbroken chain of custody, no counterfeiting detected.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-badge-failed">ALERT: FAILED AUDIT. Tampering, forgery, or counterfeit injection detected!</div>', unsafe_allow_html=True)
                
            st.markdown("### Route Stepper and Step-by-Step Proof Details:")
            
            # Render a step-by-step visual stepper
            for step in audit["history"]:
                is_ok = step["status"] == "VERIFIED"
                badge = '<span class="status-badge-verified">Verified</span>' if is_ok else '<span class="status-badge-failed">Corrupted</span>'
                
                with st.expander(f"Step {step['step_index'] + 1}: {step['node_id']} — {badge}", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Logistics Node ID:** `{step['node_id']}`")
                        st.markdown(f"**Beacon ID:** `{step['beacon_id']}`")
                        st.markdown(f"**Time Checked:** `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(step['epoch_time']))}`")
                        st.markdown(f"**Coordinates:** Latitude `{step['location']['lat']}`, Longitude `{step['location']['lon']}`")
                    
                    with c2:
                        st.markdown(f'**Transaction Hash:** <span class="mono-text">{step["tx_id"]}</span>', unsafe_allow_html=True)
                        st.markdown(f'**Previous Proof Link:** <span class="mono-text">{step["prev_proof_hash"]}</span>', unsafe_allow_html=True)
                        
                        # Show verification indicators
                        l_color = "green" if step["link_valid"] else "red"
                        s_color = "green" if step["signatures_valid"] else "red"
                        
                        st.markdown(f"**Chain Hash Match:** :{l_color}[{'Success' if step['link_valid'] else 'Broken Link'}]")
                        st.markdown(f"**Digital Signatures Match:** :{s_color}[{'Signatures Authenticated' if step['signatures_valid'] else 'Invalid Signature'}]")

                    # Demonstrate Merkle Proof extraction for students final year project!
                    st.markdown("---")
                    st.markdown("**Lightweight Verifier Merkle Verification (For Node/Client Audit)**")
                    
                    # Search root for the block containing this transaction
                    block_root = None
                    target_block = None
                    for b in blocks:
                        for tx in b["transactions"]:
                            if tx["tx_id"] == step["tx_id"]:
                                block_root = b["merkle_root"]
                                target_block = b
                                break
                    
                    if target_block and block_root:
                        tx_hashes = [t["tx_id"] for t in target_block["transactions"]]
                        tx_index = tx_hashes.index(step["tx_id"])
                        
                        from crypto.hashing import MerkleTree
                        mt = MerkleTree(tx_hashes)
                        proof = mt.get_proof(tx_index)
                        
                        st.markdown(f"- **Block Index:** `{target_block['index']}`")
                        st.markdown(f"- **Block Merkle Root:** `<span class='mono-text'>{block_root}</span>`", unsafe_allow_html=True)
                        st.markdown(f"- **Merkle Path Proof Nodes:** `{len(proof)} siblings`")
                        
                        show_proof = st.checkbox("Show Merkle Sibling Path Proof Nodes", key=f"proof_{step['tx_id']}")
                        if show_proof:
                            st.json(proof)
                            
                        # Perform verifier check in real-time
                        local_verified = MerkleTree.verify_proof(step["tx_id"], proof, block_root)
                        if local_verified:
                            st.markdown(":green[Merkle verification successful! Transaction confirmed in block structure.]")
                        else:
                            st.markdown(":red[Merkle proof mismatch. Invalid transaction membership.]")
        else:
            st.error(f"Package ID {search_pkg} was not found on the blockchain ledger.")

elif navigation == "Block Explorer":
    st.markdown("## PoA Block Explorer")
    st.markdown("Inspect blocks and pending memory pools. The PoA blockchain ledger verifies the authorization of validators before adding blocks.")

    # Section for mining pending transactions
    mempool = get_api_data("/mempool")
    
    st.markdown("### Transaction Memory Pool (Mempool)")
    if mempool:
        st.markdown(f"There are **{len(mempool)}** pending Proof-of-Location transactions waiting to be mined.")
        st.dataframe(mempool, use_container_width=True)
        
        # Mine button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Mine Pending Blocks (Authority Sign)", use_container_width=True):
                res = requests.post(f"{API_URL}/mine", json={"authority_id": "AUTHORITY-MAIN", "authority_private_key_pem": ""})
                if res.status_code == 200:
                    st.success("Block successfully mined by AUTHORITY-MAIN!")
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "Failed to mine block."))
    else:
        st.info("Mempool is empty. No new transactions waiting.")

    # Section for blockchain ledger
    st.markdown("---")
    st.markdown("### Ledger Blocks")
    chain = get_api_data("/chain")
    
    if chain:
        for block in reversed(chain):
            with st.container():
                st.markdown(f'<div class="glass-card">', unsafe_allow_html=True)
                st.markdown(f"#### Block #{block['index']} — Hash: `{block['block_hash']}`")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Index:** `{block['index']}`")
                    st.markdown(f"**Validator Authority:** `{block['authority_sig']['authority_node_id'] if block['authority_sig'] else 'None'}`")
                    st.markdown(f"**Authority Signature:** <span class='mono-text'>{block['authority_sig']['signature'][:40] if block['authority_sig'] else 'None'}...</span>", unsafe_allow_html=True)
                
                with c2:
                    st.markdown(f"**Timestamp:** `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(block['timestamp']))}`")
                    st.markdown(f"**Previous Block Hash:** `{block['prev_block_hash']}`")
                    st.markdown(f"**Merkle Root:** `{block['merkle_root']}`")
                
                st.markdown(f"**Transactions Committed ({len(block['transactions'])}):**")
                if block['transactions']:
                    st.json(block['transactions'])
                else:
                    st.caption("Genesis Block - No transactions.")
                    
                st.markdown('</div>', unsafe_allow_html=True)

elif navigation == "Security Attack Panel":
    st.markdown("## Red Team Security Testing Sandbox")
    st.markdown("Test the resilience of the Proof-of-Location protocol. Execute simulated cryptographic and network security attacks, and inspect the validation logs.")

    # Select Package to attack
    blocks = get_api_data("/chain")
    pkg_list = set()
    if blocks:
        for b in blocks:
            for tx in b["transactions"]:
                pkg_list.add(tx["pkg_id"])
                
    if not pkg_list:
        st.warning("Please initialize and run a package route simulation before using the attack simulation panel.")
        st.stop()
        
    selected_pkg = st.selectbox("Select Target Package for Attack", sorted(list(pkg_list)))
    
    # Query history to ensure it's not a completed route (so we have reference nodes)
    hist_res = requests.get(f"{API_URL}/package/history/{selected_pkg}")
    hist_data = hist_res.json()
    first_node = hist_data["history"][0]["node_id"]
    if "SHENZHEN" in first_node:
        inferred_route = "electronics_import"
    elif "WHSE" in first_node:
        inferred_route = "standard_delivery"
    else:
        inferred_route = "pharmaceuticals_cold_chain"
    
    st.markdown("---")
    st.markdown("### Choose an Attack Vector to Launch:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 1. Beacon Replay Attack")
        st.markdown("An attacker captures an attestation token (coordinates and signature) from a beacon at *Time T*, and attempts to reuse it at *Time T + 2 hours* to forge the location proof.")
        
        if st.button("Launch Replay Attack", key="btn_replay", use_container_width=True):
            with st.spinner("Executing Replay Attack..."):
                res = requests.post(f"{API_URL}/simulate/attack", params={
                    "pkg_id": selected_pkg,
                    "attack_type": "replay",
                    "route_name": inferred_route,
                    "step_index": 1
                })
                
                if res.status_code == 200:
                    data = res.json()
                    st.success("Replay attack submitted to Mempool!")
                    st.write(data)
                    st.info("The transaction signature checked out (since signatures were technically valid), but it is now in the mempool. Go to **Block Explorer** and try to mine this block. The validator will check the timestamp age and reject block creation, blocking the attack!")
                else:
                    st.error(res.json().get("detail", "Error during attack execution."))
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 2. Double-Location Fork Attack")
        st.markdown("An attacker clones a package's NFC tag, resulting in two duplicate packages. They attempt to register the package at *Shenzhen Factory* and *Dallas Warehouse* simultaneously referencing the same previous step hash.")
        
        if st.button("Launch Fork Attack", key="btn_fork", use_container_width=True):
            with st.spinner("Executing Double-Location Fork..."):
                res = requests.post(f"{API_URL}/simulate/attack", params={
                    "pkg_id": selected_pkg,
                    "attack_type": "fork",
                    "route_name": inferred_route,
                    "step_index": 1
                })
                
                if res.status_code == 200:
                    data = res.json()
                    st.success("Fork transactions injected into Mempool!")
                    st.write(data)
                    st.info("Both transactions were accepted into the mempool because their separate signatures are valid. However, since they both reference the same parent hash, mining them will create a split state fork. Try to mine this block under **Block Explorer**. The validator will catch the fork and reject the block!")
                else:
                    st.error(res.json().get("detail", "Error during attack execution."))
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 3. Signature Tampering Attack")
        st.markdown("A malicious node captures a valid Proof-of-Location packet, alters details (like package ID or coordinates), and submits it. It attempts to bypass validation with a corrupted or forged signature.")
        
        if st.button("Launch Signature Tampering", key="btn_sig", use_container_width=True):
            with st.spinner("Executing Signature Tampering..."):
                res = requests.post(f"{API_URL}/simulate/attack", params={
                    "pkg_id": selected_pkg,
                    "attack_type": "invalid_signature",
                    "route_name": inferred_route,
                    "step_index": 1
                })
                
                if res.status_code == 200:
                    data = res.json()
                    st.success("Attack blocked successfully!")
                    st.write(data)
                    st.info("The API layer immediately validated the node signature upon submission, caught the tampering, and rejected the transaction from entering the mempool. The system remains secure.")
                else:
                    st.error(res.json().get("detail", "Error during attack execution."))
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 4. Location Coordinate Forgery")
        st.markdown("A logistics node attempts to forge coordinates. They scan a package and modify the latitude/longitude coordinates (claiming they are elsewhere) but attach the original beacon's signature.")
        
        if st.button("Launch Location Forgery", key="btn_forgery", use_container_width=True):
            with st.spinner("Executing Location Forgery..."):
                res = requests.post(f"{API_URL}/simulate/attack", params={
                    "pkg_id": selected_pkg,
                    "attack_type": "gps_forgery",
                    "route_name": inferred_route,
                    "step_index": 1
                })
                
                if res.status_code == 200:
                    data = res.json()
                    st.success("Attack blocked successfully!")
                    st.write(data)
                    st.info("Because the beacon's signature signs the exact combination of BeaconID + Coordinates + Time, altering the coordinates in the transaction payload invalidates the beacon signature check. The mempool immediately rejected the submission.")
                else:
                    st.error(res.json().get("detail", "Error during attack execution."))
        st.markdown('</div>', unsafe_allow_html=True)
