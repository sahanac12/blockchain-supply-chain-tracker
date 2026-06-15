const API_URL = (window.location.protocol === "file:") ? "http://127.0.0.1:8000" : window.location.origin;
let map;
let mapMarkers = [];
let routePolyline = null;
let activeOffendingTxId = null;

let isDrawMode = false;
let drawnCheckpoints = [];
let drawnMarkers = [];
let drawnPolyline = null;

let autoTransitInterval = null;
let autoMineInterval = null;

let ROUTE_TEMPLATES = {
    "standard_delivery": [
        { id: "101", name: "Electronic City Warehouse", lat: 12.8399, lon: 77.6770 },
        { id: "102", name: "Silk Board Route Transit", lat: 12.9176, lon: 77.6244 },
        { id: "103", name: "Indiranagar Retail Store", lat: 12.9784, lon: 77.6408 }
    ],
    "electronics_import": [
        { id: "201", name: "Peenya Manufacturing Plant", lat: 13.0284, lon: 77.5197 },
        { id: "202", name: "Yeshwanthpur Cargo Depot", lat: 13.0235, lon: 77.5580 },
        { id: "203", name: "Outer Ring Road Cargo Hub", lat: 12.9304, lon: 77.6853 },
        { id: "204", name: "Whitefield Distribution Center", lat: 12.9698, lon: 77.7499 },
        { id: "205", name: "MG Road Flagship Store", lat: 12.9738, lon: 77.6119 }
    ],
    "pharmaceuticals_cold_chain": [
        { id: "301", name: "Bommasandra Biotech Lab", lat: 12.8094, lon: 77.6917 },
        { id: "302", name: "Kempegowda Airport Terminal", lat: 13.1986, lon: 77.7066 },
        { id: "303", name: "Hebbal Logistics Depot", lat: 13.0359, lon: 77.5970 },
        { id: "304", name: "Majestic Transit Terminal", lat: 12.9756, lon: 77.5728 },
        { id: "305", name: "Jayanagar Care Pharmacy", lat: 12.9299, lon: 77.5824 }
    ]
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initApp();
    });
} else {
    initApp();
}

// App Initialization
async function initApp() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    setupTabs();
    try {
        initLeafletMap();
    } catch (e) {
        console.error("Map initialization failed:", e);
        const mapEl = document.getElementById("map");
        if (mapEl) {
            mapEl.innerHTML = `<div style="padding:20px; text-align:center; color:var(--text-secondary); margin-top: 100px;">Map offline (Could not load Leaflet library)</div>`;
        }
    }
    await checkApiHealth();
    await syncLedgerData();
    
    // Poll API stats every 5 seconds to keep dashboard updated
    setInterval(async () => {
        await checkApiHealth();
        await updateStats();
    }, 5000);

    // Event Bindings
    document.getElementById("btn-initialize").addEventListener("click", initializeShipment);
    document.getElementById("btn-advance").addEventListener("click", advanceShipment);
    document.getElementById("select-active-pkg").addEventListener("change", (e) => loadPackageVisuals(e.target.value));
    document.getElementById("btn-mine").addEventListener("click", mineBlocks);
    document.getElementById("btn-audit").addEventListener("click", auditPackageChain);
    document.getElementById("btn-reset-ledger").addEventListener("click", resetLedger);
    
    // Draw Mode bindings
    document.getElementById("btn-draw-mode").addEventListener("click", toggleDrawMode);
    document.getElementById("btn-clear-draw").addEventListener("click", clearDrawnRoute);
    document.getElementById("btn-save-custom-route").addEventListener("click", saveCustomRoute);

    // Automation Toggle bindings
    document.getElementById("toggle-auto-transit").addEventListener("change", (e) => {
        if (e.target.checked) {
            autoTransitInterval = setInterval(autoTransitStep, 5000);
            showNotification("Auto-Transit active. Moving packages automatically every 5 seconds.", "success", "Automation Started");
        } else {
            clearInterval(autoTransitInterval);
            autoTransitInterval = null;
        }
    });

    document.getElementById("toggle-auto-mine").addEventListener("change", (e) => {
        if (e.target.checked) {
            autoMineInterval = setInterval(autoMineStep, 8000);
            showNotification("Auto-Mine active. Mining blocks automatically every 8 seconds.", "success", "Automation Started");
        } else {
            clearInterval(autoMineInterval);
            autoMineInterval = null;
        }
    });

    // Red Team Attack parameter range listeners
    document.getElementById("input-replay-delay").addEventListener("input", (e) => {
        const val = e.target.value;
        const hr = (val / 3600).toFixed(1);
        document.getElementById("label-replay-delay").innerText = `${val}s (${hr} hrs)`;
    });

    document.getElementById("input-gps-offset").addEventListener("input", (e) => {
        const val = parseFloat(e.target.value).toFixed(4);
        document.getElementById("label-gps-offset").innerText = `+${val}°`;
    });

    // Populate route select options dynamically
    populateRouteSelect();
    
    // Attack dropdown change binding to reload fork target nodes
    document.getElementById("select-attack-pkg").addEventListener("change", (e) => {
        populateForkNodes(e.target.value);
    });

    // Attack button bindings
    document.querySelectorAll(".btn-attack").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const attackType = e.target.getAttribute("data-attack");
            launchAttack(attackType);
        });
    });

    // Learn More button bindings
    document.querySelectorAll(".btn-learn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const attackType = e.target.getAttribute("data-learn");
            explainAttack(attackType);
        });
    });

    // Modal Close Binding
    document.getElementById("modal-close-btn").addEventListener("click", () => {
        document.getElementById("custom-modal").classList.remove("active");
    });
    document.getElementById("security-modal-close-btn").addEventListener("click", () => {
        document.getElementById("security-visual-modal").classList.remove("active");
    });
    document.getElementById("security-alert-close-btn").addEventListener("click", async () => {
        document.getElementById("security-alert-modal").classList.remove("active");
        if (activeOffendingTxId) {
            try {
                const response = await fetch(`${API_URL}/quarantine/${activeOffendingTxId}`, {
                    method: "POST"
                });
                if (response.ok) {
                    showNotification("Attack transaction quarantined successfully.", "success", "Transaction Isolated");
                    activeOffendingTxId = null;
                    await syncLedgerData();
                    // Wait 1 second and resume mining
                    setTimeout(async () => {
                        await mineBlocks();
                    }, 1000);
                } else {
                    const err = await response.json();
                    showNotification(`Failed to quarantine: ${err.detail}`, "error", "Isolation Error");
                }
            } catch (e) {
                showNotification("API Connection Error during quarantine execution", "error", "Connection Failed");
            }
        }
    });
}

// Tab Switching DOM logic
function setupTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            navButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
            
            // Relayout Leaflet Map when switching back to Simulation tab
            if (targetTab === "simulation-tab" && map) {
                setTimeout(() => map.invalidateSize(), 100);
            }
        });
    });
}

// Map Initialization
function initLeafletMap() {
    // Default centering to Bangalore
    map = L.map("map").setView([12.9716, 77.5946], 11);
    
    // Load Dark Matter Map tiles
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // Dynamic checkpoint drawing click handler
    map.on("click", (e) => {
        if (isDrawMode) {
            addDrawnCheckpoint(e.latlng.lat, e.latlng.lng);
        }
    });
}

// Check Backend API Connection Status
async function checkApiHealth() {
    const statusBox = document.getElementById("connection-status");
    try {
        const response = await fetch(`${API_URL}/status`);
        if (response.ok) {
            statusBox.innerHTML = `<span class="status-indicator green"></span> Connected to API`;
            return true;
        }
    } catch (e) {
        statusBox.innerHTML = `<span class="status-indicator red"></span> Offline (FastAPI Port 8000)`;
    }
    return false;
}

// Sync Ledger and Statistics
async function syncLedgerData() {
    await updateStats();
    await populateActivePackages();
    await loadBlockChainList();
    await loadMempoolList();
    await loadQuarantineList();
}

async function updateStats() {
    try {
        const response = await fetch(`${API_URL}/status`);
        if (response.ok) {
            const data = await response.json();
            document.getElementById("stat-blocks").innerText = data.blocks_count;
            document.getElementById("stat-mempool").innerText = data.pending_transactions_count;
            document.getElementById("stat-beacons").innerText = data.registered_beacons;
            document.getElementById("stat-nodes").innerText = data.registered_nodes;
        }
    } catch(e) {}
}

// Populate Dropdowns with active packages
async function populateActivePackages() {
    const dropdownSim = document.getElementById("select-active-pkg");
    const dropdownAttack = document.getElementById("select-attack-pkg");
    
    try {
        const response = await fetch(`${API_URL}/chain`);
        const mempoolRes = await fetch(`${API_URL}/mempool`);
        
        const activePkgs = new Set();
        
        if (response.ok) {
            const chain = await response.json();
            chain.forEach(block => {
                block.transactions.forEach(tx => activePkgs.add(tx.pkg_id));
            });
        }
        
        if (mempoolRes.ok) {
            const mempool = await mempoolRes.json();
            mempool.forEach(tx => activePkgs.add(tx.pkg_id));
        }

        // Clear and rebuild options
        const currentSelectionSim = dropdownSim.value;
        const currentSelectionAttack = dropdownAttack.value;

        dropdownSim.innerHTML = `<option value="">-- Select Active Package --</option>`;
        dropdownAttack.innerHTML = `<option value="">-- Select Target Package --</option>`;

        Array.from(activePkgs).sort().forEach(pkg => {
            dropdownSim.innerHTML += `<option value="${pkg}">${pkg}</option>`;
            dropdownAttack.innerHTML += `<option value="${pkg}">${pkg}</option>`;
        });

        // Restore prior selections if possible
        if (activePkgs.has(currentSelectionSim)) dropdownSim.value = currentSelectionSim;
        if (activePkgs.has(currentSelectionAttack)) {
            dropdownAttack.value = currentSelectionAttack;
            populateForkNodes(currentSelectionAttack);
        }
        
    } catch(e) {}
}

// API Trigger: Initialize Package Scan
async function initializeShipment() {
    const pkgId = document.getElementById("input-pkg-id").value.trim();
    const routeName = document.getElementById("select-route").value;
    
    if (!pkgId) {
        showNotification("Please enter a Package ID", "error", "Input Missing");
        return;
    }
    
    // Check if package has already been initialized
    const history = await fetchCombinedHistory(pkgId);
    if (history.length > 0) {
        showNotification(`Package ${pkgId} has already been initialized. Use the "Move Package Forward" panel to register subsequent scans.`, "info", "Already Initialized");
        return;
    }
    
    const latVal = document.getElementById("input-init-lat").value.trim();
    const lonVal = document.getElementById("input-init-lon").value.trim();
    const bodyObj = { pkg_id: pkgId, route_name: routeName };
    if (latVal !== "" && lonVal !== "") {
        bodyObj.latitude = parseFloat(latVal);
        bodyObj.longitude = parseFloat(lonVal);
    }
    
    try {
        const response = await fetch(`${API_URL}/simulate/step`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyObj)
        });
        
        if (response.ok) {
            const data = await response.json();
            showNotification(`Shipment Initialized! Scanned at: ${data.location}`, "success", "Scan Success");
            await syncLedgerData();
            document.getElementById("select-active-pkg").value = pkgId;
            loadPackageVisuals(pkgId);
        } else {
            const err = await response.json();
            showNotification(`Failed: ${err.detail}`, "error", "Simulation Error");
        }
    } catch (e) {
        showNotification("API Connection Error", "error", "Connection Failed");
    }
}

// API Trigger: Register Next Location Scan
async function advanceShipment() {
    const selectedPkg = document.getElementById("select-active-pkg").value;
    if (!selectedPkg) {
        showNotification("Please select a package in transit", "error", "Selection Missing");
        return;
    }
    
    // Infer the route template by checking package history
    const inferredRoute = await inferRouteForPackage(selectedPkg);
    
    // Check if package has already completed this route
    const history = await fetchCombinedHistory(selectedPkg);
    const maxSteps = ROUTE_TEMPLATES[inferredRoute].length;
    if (history.length >= maxSteps) {
        showNotification(`Package ${selectedPkg} has already completed the route.`, "info", "Route Completed");
        return;
    }
    
    const latVal = document.getElementById("input-move-lat").value.trim();
    const lonVal = document.getElementById("input-move-lon").value.trim();
    const bodyObj = { pkg_id: selectedPkg, route_name: inferredRoute };
    if (latVal !== "" && lonVal !== "") {
        bodyObj.latitude = parseFloat(latVal);
        bodyObj.longitude = parseFloat(lonVal);
    }
    
    try {
        const response = await fetch(`${API_URL}/simulate/step`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyObj)
        });
        
        if (response.ok) {
            const data = await response.json();
            showNotification(`Advanced Scan! Location: ${data.location}`, "success", "Scan Success");
            
            // Clear inputs
            document.getElementById("input-move-lat").value = "";
            document.getElementById("input-move-lon").value = "";
            
            await syncLedgerData();
            loadPackageVisuals(selectedPkg);
        } else {
            const err = await response.json();
            showNotification(`Failed: ${err.detail}`, "error", "Simulation Error");
        }
    } catch (e) {
        showNotification("API Connection Error", "error", "Connection Failed");
    }
}

async function inferRouteForPackage(pkgId) {
    try {
        const res = await fetch(`${API_URL}/package/history/${pkgId}`);
        if (res.ok) {
            const data = await res.json();
            const firstNode = data.history[0].node_id;
            if (firstNode.includes("SHENZHEN")) return "electronics_import";
            if (firstNode.includes("WHSE")) return "standard_delivery";
            return "pharmaceuticals_cold_chain";
        }
    } catch(e) {}
    return "standard_delivery";
}

// Fetch Combined Mempool & Confirmed History
async function fetchCombinedHistory(pkgId) {
    let history = [];
    try {
        const res = await fetch(`${API_URL}/package/history/${pkgId}`);
        if (res.ok) {
            const data = await res.json();
            history = data.history;
        }
    } catch(e) {}
    
    try {
        const res = await fetch(`${API_URL}/mempool`);
        if (res.ok) {
            const mempool = await res.json();
            const pkgMempool = mempool.filter(tx => tx.pkg_id === pkgId).sort((a,b) => a.epoch_time - b.epoch_time);
            
            const startIndex = history.length;
            pkgMempool.forEach((tx, idx) => {
                history.push({
                    step_index: startIndex + idx,
                    tx_id: tx.tx_id,
                    pkg_id: tx.pkg_id,
                    node_id: tx.node_id,
                    beacon_id: tx.beacon_id,
                    location: tx.location,
                    epoch_time: tx.epoch_time,
                    prev_proof_hash: tx.prev_proof_hash,
                    link_valid: true,
                    signatures_valid: true,
                    status: "PENDING_MINING"
                });
            });
        }
    } catch(e) {}
    return history;
}

// Render dynamic path markers on Map and build Stepper in DOM
async function loadPackageVisuals(pkgId) {
    if (!pkgId) {
        document.getElementById("progress-stepper-container").innerHTML = "";
        clearMapVisuals();
        return;
    }
    
    const inferredRoute = await inferRouteForPackage(pkgId);
    document.getElementById("selected-package-path-title").innerText = 
        `Selected Package Path: ${pkgId} (${inferredRoute.replace(/_/g, ' ').toUpperCase()})`;
    
    const history = await fetchCombinedHistory(pkgId);
    const historyNodes = {};
    history.forEach(step => historyNodes[step.node_id] = step);
    
    const routeSteps = ROUTE_TEMPLATES[inferredRoute];
    
    // --- PART 1: DRAW DOM STEPPER PROGRESS BAR ---
    let stepperHtml = `<div class="stepper-container">`;
    for (let i = 0; i < routeSteps.length; i++) {
        const step = routeSteps[i];
        const nodeID = `NODE-${step.id}`;
        
        let icon = "";
        if (nodeID.includes("TRUCK")) icon = "";
        else if (nodeID.includes("RETAIL") || nodeID.includes("STORE") || nodeID.includes("PHARMA")) icon = "";
        else if (nodeID.includes("PORT") || nodeID.includes("AIR")) icon = "";
        
        const record = historyNodes[nodeID];
        let circleClass = "";
        let statusLabel = "Not Reached";
        let lineClass = "";
        
        if (record) {
            if (record.status === "PENDING_MINING") {
                circleClass = "mempool";
                statusLabel = "In Mempool";
            } else {
                circleClass = "confirmed";
                statusLabel = "Confirmed";
            }
        }
        
        stepperHtml += `
            <div class="step-node">
                <div class="step-circle ${circleClass}">${icon}</div>
                <div class="step-name">${step.name}</div>
                <div style="font-size: 0.65rem; font-weight: 600; margin-top: 2px; color: ${circleClass === 'confirmed' ? 'var(--success-green)' : circleClass === 'mempool' ? 'var(--warning-yellow)' : 'var(--text-secondary)'}">${statusLabel}</div>
            </div>
        `;
        
        if (i < routeSteps.length - 1) {
            const nextNode = `NODE-${routeSteps[i+1].id}`;
            const nextReached = historyNodes[nextNode];
            let activeLineClass = "";
            if (record && nextReached) {
                activeLineClass = nextReached.status === "PENDING_MINING" ? "mempool" : "active";
            }
            stepperHtml += `<div class="step-line ${activeLineClass}"></div>`;
        }
    }
    stepperHtml += `</div>`;
    document.getElementById("progress-stepper-container").innerHTML = stepperHtml;
    
    // --- PART 2: DRAW DYNAMIC MAP PLOTS ---
    clearMapVisuals();
    
    if (typeof L !== 'undefined' && map) {
        const latLngs = [];
        history.forEach(step => {
            const lat = step.location.lat;
            const lon = step.location.lon;
            latLngs.push([lat, lon]);
            
            const isMempool = step.status === "PENDING_MINING";
            
            // Define Custom Marker Colors
            const marker = L.circleMarker([lat, lon], {
                radius: 8,
                fillColor: isMempool ? "#F59E0B" : "#10B981",
                color: "#FFFFFF",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            
            marker.bindPopup(`
                <strong>${step.node_id}</strong><br/>
                Status: ${isMempool ? 'Pending Block' : 'Confirmed on Chain'}<br/>
                Time: ${new Date(step.epoch_time * 1000).toLocaleString()}
            `);
            
            mapMarkers.push(marker);
        });
        
        if (latLngs.length > 0) {
            // Draw Polyline path
            routePolyline = L.polyline(latLngs, {
                color: "#60A5FA",
                weight: 3,
                dashArray: "5, 8",
                opacity: 0.7
            }).addTo(map);
            
            // Pan and fit map window around trace
            map.fitBounds(L.latLngBounds(latLngs), { padding: [50, 50] });
        }
    }
}

function clearMapVisuals() {
    if (typeof L !== 'undefined' && map) {
        mapMarkers.forEach(m => map.removeLayer(m));
        mapMarkers = [];
        if (routePolyline) {
            map.removeLayer(routePolyline);
            routePolyline = null;
        }
    }
}

// API Trigger: Mine blocks under PoA
async function mineBlocks() {
    try {
        const response = await fetch(`${API_URL}/mine`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ authority_id: "AUTHORITY-MAIN", authority_private_key_pem: "" })
        });
        
        if (response.ok) {
            const data = await response.json();
            showNotification("Success: Block mined under Authority Signatures.", "success", "Consensus Signed");
            await syncLedgerData();
            
            // Reload active package visual states
            const activePkg = document.getElementById("select-active-pkg").value;
            if (activePkg) loadPackageVisuals(activePkg);
        } else {
            const err = await response.json();
            if (err.detail && err.detail.includes("Consensus Validation Block Rejected:")) {
                stopAutoMine();
                showAttackBlockedModal(err.detail);
            } else {
                showNotification(`Failed: ${err.detail}`, "error", "Mining Rejected");
            }
        }
    } catch(e) {
        showNotification("API Connection Error", "error", "Connection Failed");
    }
}

// DOM Explorer: Render Ledger Block lists
async function loadBlockChainList() {
    const container = document.getElementById("block-chain-container");
    container.innerHTML = `<h3>Ledger Blocks</h3>`;
    
    try {
        const response = await fetch(`${API_URL}/chain`);
        if (response.ok) {
            const chain = await response.json();
            
            // Render blocks reversed (latest first)
            chain.slice().reverse().forEach(block => {
                const header = block.authority_sig;
                const blockHtml = `
                    <div class="block-card">
                        <div class="block-header-info">
                            <div><strong>Block #${block.index}</strong> — Hash: <span class="mono">${block.block_hash.slice(0, 16)}...</span></div>
                            <div>Validator: <span class="mono">${header ? header.authority_node_id : 'GENESIS'}</span></div>
                        </div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;">
                            Time: ${new Date(block.timestamp * 1000).toLocaleString()} | Merkle Root: <span class="mono">${block.merkle_root.slice(0, 12)}...</span>
                        </div>
                        <div style="font-size: 0.8rem; font-weight: 600; margin-bottom: 4px;">Committed Transactions (${block.transactions.length})</div>
                        <pre style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; font-size: 0.75rem; color: #93C5FD; max-height: 150px; overflow-y: auto;">${JSON.stringify(block.transactions, null, 2)}</pre>
                    </div>
                `;
                container.innerHTML += blockHtml;
            });
        }
    } catch(e) {}
}

// DOM Explorer: Render Mempool contents
function checkMempoolTransactionStatus(tx, mempool) {
    // 1. Replay Attack Check
    const ageSeconds = Math.round(Date.now() / 1000) - tx.epoch_time;
    if (ageSeconds > 300) {
        return {
            isAttack: true,
            type: "Beacon Replay Attack",
            reason: `Freshness limit exceeded: attestation is ${Math.round(ageSeconds / 60)} mins old (Max: 5 mins).`
        };
    }
    
    // 2. Double-Location Fork Check
    const conflicts = mempool.filter(item => 
        item.tx_id !== tx.tx_id && 
        item.pkg_id === tx.pkg_id && 
        item.prev_proof_hash === tx.prev_proof_hash
    );
    if (conflicts.length > 0) {
        return {
            isAttack: true,
            type: "Double-Location Fork Attack",
            reason: `Conflicting fork path: multiple transactions branch from parent hash ${tx.prev_proof_hash.slice(0, 8)}...`
        };
    }
    
    return { isAttack: false };
}

async function loadMempoolList() {
    const tableBody = document.querySelector("#mempool-table tbody");
    const countLabel = document.getElementById("mempool-count-label");
    
    try {
        const response = await fetch(`${API_URL}/mempool`);
        if (response.ok) {
            const mempool = await response.json();
            countLabel.innerText = `${mempool.length} pending transaction(s)`;
            
            if (mempool.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="6" class="center-text">Mempool is empty.</td></tr>`;
                return;
            }
            
            tableBody.innerHTML = "";
            mempool.forEach(tx => {
                const tr = document.createElement("tr");
                const check = checkMempoolTransactionStatus(tx, mempool);
                
                if (check.isAttack) {
                    tr.style.background = "rgba(239, 68, 68, 0.08)";
                    tr.style.borderLeft = "4px solid var(--danger-red)";
                    tr.innerHTML = `
                        <td>${tx.pkg_id}</td>
                        <td>${tx.node_id}</td>
                        <td>${tx.beacon_id}</td>
                        <td>${tx.location.lat.toFixed(4)}, ${tx.location.lon.toFixed(4)}</td>
                        <td>${new Date(tx.epoch_time * 1000).toLocaleTimeString()}</td>
                        <td>
                            <div style="display: flex; flex-direction: column; gap: 2px;">
                                <span style="color: var(--danger-red); font-weight: 700;">⚠️ ${check.type}</span>
                                <span style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.2;">${check.reason}</span>
                            </div>
                        </td>
                    `;
                } else {
                    tr.innerHTML = `
                        <td>${tx.pkg_id}</td>
                        <td>${tx.node_id}</td>
                        <td>${tx.beacon_id}</td>
                        <td>${tx.location.lat.toFixed(4)}, ${tx.location.lon.toFixed(4)}</td>
                        <td>${new Date(tx.epoch_time * 1000).toLocaleTimeString()}</td>
                        <td><span style="color: var(--warning-yellow); font-weight: 600;">Pending Mining</span></td>
                    `;
                }
                tableBody.appendChild(tr);
            });
        }
    } catch(e) {}
}

// DOM Auditor: Run full forensic provenance audit
async function auditPackageChain() {
    const pkgId = document.getElementById("search-pkg-input").value.trim();
    const timeline = document.getElementById("audit-history-timeline");
    const badgeBox = document.getElementById("audit-status-badge");

    if (!pkgId) {
        showNotification("Please enter a Package ID to audit.", "error", "Input Required");
        return;
    }

    // --- Animated Loading State ---
    badgeBox.innerHTML = "";
    timeline.innerHTML = `
        <div class="audit-loading-panel">
            <div class="audit-loading-title">🔬 Initiating Forensic Audit Scan</div>
            <div class="audit-loading-steps">
                <div class="audit-loading-step active" id="als-1">📡 Querying confirmed blockchain ledger...</div>
                <div class="audit-loading-step" id="als-2">🔍 Cross-referencing quarantine log...</div>
                <div class="audit-loading-step" id="als-3">🧪 Scanning live mempool for threats...</div>
                <div class="audit-loading-step" id="als-4">🔐 Generating cryptographic forensic report...</div>
            </div>
        </div>`;

    const stepIds = ["als-1","als-2","als-3","als-4"];
    let si = 0;
    const stepInterval = setInterval(() => {
        if (si > 0) document.getElementById(stepIds[si-1])?.classList.remove("active");
        if (si < stepIds.length) { document.getElementById(stepIds[si])?.classList.add("active"); si++; }
    }, 380);

    // --- Parallel Data Fetch ---
    let historyData = null, quarantined = [], mempool = [];
    try {
        const [histRes, quarRes, mempoolRes] = await Promise.all([
            fetch(`${API_URL}/package/history/${pkgId}`),
            fetch(`${API_URL}/quarantine`),
            fetch(`${API_URL}/mempool`)
        ]);
        clearInterval(stepInterval);
        if (!histRes.ok) {
            timeline.innerHTML = `<p class="info-text" style="color:var(--danger-red);">Package <strong>${pkgId}</strong> was not found on the blockchain ledger. No provenance records exist.</p>`;
            return;
        }
        historyData = await histRes.json();
        if (quarRes.ok) quarantined = await quarRes.json();
        if (mempoolRes.ok) mempool = await mempoolRes.json();
    } catch(e) {
        clearInterval(stepInterval);
        timeline.innerHTML = "<p>Error connecting to API during audit. Ensure the backend is running.</p>";
        return;
    }

    // --- Attack Meta-Knowledge Base ---
    const ATTACK_META = {
        "Beacon Replay Attack": {
            severity: "HIGH", sevColor: "var(--warning-yellow)",
            how: "The Proof-of-Authority validator checks each attestation token's cryptographic timestamp against the current system clock. This token's epoch_time exceeded the enforced 300-second (5-minute) freshness window — a hard limit signed into every block by the consensus quorum.",
            why: "Replay attacks fabricate false package progress. A criminal intercepts a valid location token from a legitimate past scan, then re-submits it hours later from a different physical location to fake delivery milestones, cover cargo theft, or bypass checkpoint controls.",
            mitigation: "Token was flagged during consensus validation. The PoA quorum (AUTHORITY-PRODUCER, AUTHORITY-CARRIER, AUTHORITY-RETAILER) refused to sign the block containing the stale attestation, causing block rejection."
        },
        "Double-Location Fork Attack": {
            severity: "CRITICAL", sevColor: "var(--danger-red)",
            how: "The validator detected two transactions for the same package sharing an identical prev_proof_hash parent reference. Since each scan must extend from the previous unique scan hash, two competing transactions branching from the same parent hash is a physical impossibility for a single package — indicating simultaneous dual-location scanning.",
            why: "Fork attacks are the primary counterfeit injection vector. Criminals clone a package's RFID/NFC security tag identity, then scan the clone at a separate node to inject a parallel false custody chain. This introduces counterfeit goods alongside genuine shipments or enables double-insurance fraud.",
            mitigation: "The consensus validator's double-spend detector flagged the conflicting chain branch. The block was rejected and the offending fork transaction quarantined before any ledger corruption occurred."
        },
        "Node Signature Tampering": {
            severity: "CRITICAL", sevColor: "var(--danger-red)",
            how: "The logistics gateway node's RSA-2048 cryptographic signature over the scan payload failed verification against the node's registered public key in the blockchain registry. The payload fields were modified after signing, invalidating the mathematical signature.",
            why: "Tampering is executed via Man-in-the-Middle (MitM) interception. Attackers intercept a signed location packet in transit and alter timestamps, location IDs, or coordinates to modify historical records — concealing route deviations, faking SLA compliance, or backdating deliveries.",
            mitigation: "The API gateway's signature verification filter rejected the transaction at mempool submission — before it could corrupt the pending queue. The tampered packet never reached the blockchain layer."
        },
        "Location Coordinate Forgery": {
            severity: "HIGH", sevColor: "var(--warning-yellow)",
            how: "The GPS coordinates reported in the transaction did not match the coordinates cryptographically signed into the beacon's hardware attestation token. The LocalAttestationBeacon signs location data at the hardware level; any post-signing coordinate modification breaks the beacon's ECDSA signature.",
            why: "Coordinate forgery allows malicious drivers or nodes to report false GPS positions — claiming a package reached a distant hub without physically transporting it. This enables SLA milestone fraud, smuggling route concealment, and falsified customs compliance.",
            mitigation: "Beacon signature verification detected the coordinate mismatch at the API gateway. The forged transaction was blocked during mempool submission."
        },
        "Consensus Violation": {
            severity: "HIGH", sevColor: "var(--warning-yellow)",
            how: "The block containing this transaction failed the Proof-of-Authority quorum consensus check. The required majority of the three registered validator authorities could not reach agreement to sign the block.",
            why: "A consensus violation indicates the transaction data was flagged as suspicious by the validator network.",
            mitigation: "Block was rejected by the consensus mechanism. No ledger corruption occurred."
        }
    };

    // --- Threat Detection ---
    const pkgQuarantined = quarantined.filter(tx => tx.pkg_id === pkgId);
    const pkgMempool = mempool.filter(tx => tx.pkg_id === pkgId);
    const mempoolThreats = [];
    pkgMempool.forEach(tx => {
        const age = Math.round(Date.now() / 1000) - tx.epoch_time;
        if (age > 300 && !mempoolThreats.find(t => t.tx_id === tx.tx_id)) {
            mempoolThreats.push({ type: "Beacon Replay Attack", tx_id: tx.tx_id, node_id: tx.node_id,
                beacon_id: tx.beacon_id, epoch_time: tx.epoch_time, source: "MEMPOOL",
                reason: `Attestation token is ${Math.round(age/60)} minutes old (freshness limit: 5 min). Token was captured from a past scan and replayed.` });
        }
        const forks = pkgMempool.filter(o => o.tx_id !== tx.tx_id && o.prev_proof_hash === tx.prev_proof_hash);
        if (forks.length > 0 && !mempoolThreats.find(t => t.tx_id === tx.tx_id)) {
            mempoolThreats.push({ type: "Double-Location Fork Attack", tx_id: tx.tx_id, node_id: tx.node_id,
                beacon_id: tx.beacon_id, epoch_time: tx.epoch_time, source: "MEMPOOL",
                reason: `Fork from parent hash ${tx.prev_proof_hash.slice(0,12)}... — two concurrent location proofs for the same package state.` });
        }
    });

    const allThreats = [
        ...pkgQuarantined.map(tx => ({ type: tx.threat_type, tx_id: tx.tx_id, node_id: tx.node_id,
            beacon_id: tx.beacon_id, reason: tx.reason, epoch_time: tx.quarantine_time, source: "QUARANTINE" })),
        ...mempoolThreats
    ];

    const counterfeiting = allThreats.length > 0 || !historyData.is_provenance_valid;
    const auditTime = new Date().toLocaleString();
    const verifiedCount = historyData.history.filter(s => s.status === "VERIFIED").length;
    const totalCount = historyData.history.length;
    const criticalCount = allThreats.filter(t => (ATTACK_META[t.type]?.severity) === "CRITICAL").length;
    const uniqueNodes = [...new Set(allThreats.map(t => t.node_id))];

    // Store for export
    window._lastAuditData = { pkgId, historyData, allThreats, counterfeiting, auditTime };

    // --- Status Badge ---
    if (counterfeiting) {
        badgeBox.innerHTML = `<span class="audit-badge failed">⚠️ COUNTERFEITING DETECTED — ${allThreats.length} Threat(s) Found</span>`;
    } else {
        badgeBox.innerHTML = `<span class="audit-badge verified">✅ PROVENANCE VERIFIED: Unbroken chain of custody, no counterfeiting detected.</span>`;
    }

    // ========== BUILD REPORT ==========
    let html = "";

    // 1. Executive Summary
    const ec = counterfeiting ? "var(--danger-red)" : "var(--success-green)";
    const eb = counterfeiting ? "rgba(239,68,68,0.08)" : "rgba(52,211,153,0.06)";
    const ebr = counterfeiting ? "rgba(239,68,68,0.25)" : "rgba(52,211,153,0.25)";
    const verdict = counterfeiting ? "⚠️ COUNTERFEITING DETECTED" : "✅ PROVENANCE CLEAR";
    const verdictSub = counterfeiting
        ? `${allThreats.length} active threat(s) detected in system logs. Immediate investigation required.`
        : "All cryptographic signatures verified. Unbroken chain of custody confirmed across all checkpoints.";

    html += `
        <div class="audit-exec-summary" style="background:${eb}; border:1px solid ${ebr};">
            <div class="audit-exec-verdict" style="color:${ec};">${verdict}</div>
            <div class="audit-exec-sub">${verdictSub}</div>
            <div class="audit-exec-stats">
                <div class="audit-exec-stat">
                    <div class="audit-exec-stat-val">${totalCount}</div>
                    <div class="audit-exec-stat-lbl">Scan Steps</div>
                </div>
                <div class="audit-exec-stat">
                    <div class="audit-exec-stat-val" style="color:var(--success-green);">${verifiedCount}</div>
                    <div class="audit-exec-stat-lbl">Verified</div>
                </div>
                <div class="audit-exec-stat">
                    <div class="audit-exec-stat-val" style="color:${allThreats.length>0?'var(--danger-red)':'var(--success-green)'};">${allThreats.length}</div>
                    <div class="audit-exec-stat-lbl">Threats</div>
                </div>
                <div class="audit-exec-stat">
                    <div class="audit-exec-stat-val" style="color:${criticalCount>0?'var(--danger-red)':'var(--success-green)'};">${criticalCount}</div>
                    <div class="audit-exec-stat-lbl">Critical</div>
                </div>
                <div class="audit-exec-stat">
                    <div class="audit-exec-stat-val" style="color:var(--accent-purple);">${uniqueNodes.length}</div>
                    <div class="audit-exec-stat-lbl">Nodes Flagged</div>
                </div>
            </div>
            <div style="font-size:0.7rem; color:var(--text-secondary); margin-top:10px; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;">
                🕒 Audit generated: ${auditTime} &nbsp;|&nbsp; Package ID: <span class="mono" style="font-size:0.7rem;">${pkgId}</span>
            </div>
        </div>`;

    // 2. Report Action Buttons
    html += `
        <div class="audit-report-actions">
            <button class="btn secondary" onclick="exportAuditReport('${pkgId}')" style="width:auto; padding:7px 16px; font-size:0.8rem; display:flex; align-items:center; gap:6px;">📥 Export JSON Report</button>
            <button class="btn secondary" onclick="copyAuditSummary('${pkgId}', ${counterfeiting}, ${allThreats.length})" style="width:auto; padding:7px 16px; font-size:0.8rem; display:flex; align-items:center; gap:6px;">📋 Copy Summary</button>
            <button class="btn secondary" onclick="window.print()" style="width:auto; padding:7px 16px; font-size:0.8rem; display:flex; align-items:center; gap:6px;">🖨️ Print Report</button>
        </div>`;

    // 3. Threat Intelligence Cards
    if (allThreats.length > 0) {
        html += `<div class="audit-section-label">🛡️ Threat Intelligence Report</div>`;
        allThreats.forEach((threat, i) => {
            const meta = ATTACK_META[threat.type] || ATTACK_META["Consensus Violation"];
            const timeStr = new Date(threat.epoch_time * 1000).toLocaleString();
            const srcColor = threat.source === "QUARANTINE" ? "var(--danger-red)" : "var(--warning-yellow)";
            const srcLbl = threat.source === "QUARANTINE" ? "🔒 QUARANTINED & ISOLATED" : "⏳ LIVE IN MEMPOOL";
            html += `
                <div class="audit-threat-card">
                    <div class="audit-threat-card-hdr">
                        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                            <span class="audit-sev-badge" style="background:${meta.sevColor}18; color:${meta.sevColor}; border:1px solid ${meta.sevColor}40;">${meta.severity}</span>
                            <span class="audit-threat-title">Threat #${i+1}: ${threat.type}</span>
                        </div>
                        <span class="audit-src-badge" style="color:${srcColor};">${srcLbl}</span>
                    </div>
                    <div class="audit-threat-meta-grid">
                        <div><span class="audit-lbl">Offending Node</span><span class="mono">${threat.node_id}</span></div>
                        <div><span class="audit-lbl">Beacon</span><span class="mono">${threat.beacon_id}</span></div>
                        <div><span class="audit-lbl">Transaction ID</span><span class="mono">${threat.tx_id.slice(0,24)}...</span></div>
                        <div><span class="audit-lbl">Flagged At</span>${timeStr}</div>
                    </div>
                    <div class="audit-raw-reason">
                        <div class="audit-raw-reason-lbl">⚙️ Raw Detection Signal</div>
                        <div class="audit-raw-reason-txt">${threat.reason}</div>
                    </div>
                    <div class="audit-how-why-grid">
                        <div class="audit-how-box">
                            <div class="audit-how-title">🔬 How Was This Detected?</div>
                            <p>${meta.how}</p>
                        </div>
                        <div class="audit-why-box">
                            <div class="audit-why-title">💀 Why Is This Counterfeiting?</div>
                            <p>${meta.why}</p>
                        </div>
                    </div>
                    <div class="audit-mitigation-box">
                        <div class="audit-mitigation-title">🛡️ System Defense & Mitigation Applied</div>
                        <p>${meta.mitigation}</p>
                    </div>
                </div>`;
        });

        // 4. Forensic Trace & Recommended Actions
        html += `<div class="audit-section-label">🔎 Forensic Trace — Recommended Investigation Actions</div>
            <div class="audit-trace-panel">
                <div class="audit-trace-step">
                    <div class="audit-trace-num">1</div>
                    <div class="audit-trace-content">
                        <strong>Place Shipment on Immediate Physical Hold</strong>
                        <p>Quarantine package <span class="mono">${pkgId}</span> and halt all further transit. Do not allow delivery or customs clearance until forensic investigation is complete.</p>
                    </div>
                </div>
                <div class="audit-trace-step">
                    <div class="audit-trace-num">2</div>
                    <div class="audit-trace-content">
                        <strong>Conduct Physical Security Audit of Flagged Nodes</strong>
                        <p>Dispatch forensic teams to: ${uniqueNodes.map(n=>`<span class="mono">${n}</span>`).join(', ')}. Inspect for RFID/NFC tag clones, rogue scanner installations, compromised firmware, or unauthorized personnel access.</p>
                    </div>
                </div>
                <div class="audit-trace-step">
                    <div class="audit-trace-num">3</div>
                    <div class="audit-trace-content">
                        <strong>Cross-Reference Physical Inventory Count</strong>
                        <p>Perform an immediate physical inventory count at all checkpoints in the verified chain below. Compare physical quantities against the ${verifiedCount} confirmed blockchain scan records to identify substituted or missing goods.</p>
                    </div>
                </div>
                <div class="audit-trace-step">
                    <div class="audit-trace-num">4</div>
                    <div class="audit-trace-content">
                        <strong>Export Report & File Compliance Incident</strong>
                        <p>Download this audit report using <strong>Export JSON Report</strong> above. Submit a formal incident report to your supply chain security team, customs authority, and any relevant regulatory bodies (e.g., FDA for pharmaceuticals, ICC for trade fraud).</p>
                    </div>
                </div>
                <div class="audit-trace-step">
                    <div class="audit-trace-num">5</div>
                    <div class="audit-trace-content">
                        <strong>Revoke & Rotate Compromised Cryptographic Keys</strong>
                        <p>If node signature tampering was detected, immediately revoke and re-issue RSA keypairs for all flagged nodes from the blockchain registry. Re-register updated public keys before resuming operations on this route.</p>
                    </div>
                </div>
            </div>`;
    }

    // 5. Provenance Chain Timeline
    html += `<div class="audit-section-label">📦 Verified Blockchain Chain-of-Custody (${historyData.steps_count} confirmed steps)</div>`;
    historyData.history.forEach((step, idx) => {
        const dateStr = new Date(step.epoch_time * 1000).toLocaleString();
        const linkedThreat = allThreats.find(t => t.node_id === step.node_id);
        const cardBorder = linkedThreat
            ? "border-left: 3px solid var(--danger-red);"
            : "border-left: 3px solid var(--success-green);";
        const attackAnnotation = linkedThreat
            ? `<div class="verif-indicator fail" style="margin-top:8px;">⚠️ Attack attempted via this node: ${linkedThreat.type}</div>` : "";
        html += `
            <div class="audit-card" style="${cardBorder}">
                <h4>Step ${idx+1}: ${step.node_id}
                    <span style="color:${step.status==='VERIFIED'?'var(--success-green)':'var(--danger-red)'}">${step.status}</span>
                </h4>
                <div class="audit-columns">
                    <div class="audit-meta">
                        <p><strong>Beacon ID:</strong> ${step.beacon_id}</p>
                        <p><strong>Coordinates:</strong> ${step.location.lat.toFixed(4)}, ${step.location.lon.toFixed(4)}</p>
                        <p><strong>Timestamp:</strong> ${dateStr}</p>
                    </div>
                    <div class="audit-hashes">
                        <p><strong>Tx Hash:</strong> <span class="mono">${step.tx_id.slice(0,24)}...</span></p>
                        <p><strong>Prev Link:</strong> <span class="mono">${step.prev_proof_hash.slice(0,24)}...</span></p>
                        <div class="verif-indicator ${step.link_valid?'success':'fail'}">
                            Chain Linkage: ${step.link_valid?'Verified':'Broken'}
                        </div>
                        <div class="verif-indicator ${step.signatures_valid?'success':'fail'}">
                            Digital Signatures: ${step.signatures_valid?'Authenticated':'Invalid Signature'}
                        </div>
                        ${attackAnnotation}
                    </div>
                </div>
            </div>`;
    });

    timeline.innerHTML = html;
}

// Export audit report as JSON download
function exportAuditReport(pkgId) {
    const data = window._lastAuditData;
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `POL_Audit_${pkgId}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification(`Forensic audit report exported for ${pkgId}.`, "success", "Export Complete");
}

// Copy audit summary to clipboard
async function copyAuditSummary(pkgId, counterfeiting, threatCount) {
    const status = counterfeiting ? `⚠️ COUNTERFEITING DETECTED — ${threatCount} threat(s) found` : "✅ PROVENANCE VERIFIED — No counterfeiting detected";
    const text = `POL Forensic Audit Report\n${"=".repeat(40)}\nPackage ID: ${pkgId}\nStatus: ${status}\nGenerated: ${new Date().toLocaleString()}\nSystem: POL Supply Chain Provenance Console`;
    try {
        await navigator.clipboard.writeText(text);
        showNotification("Audit summary copied to clipboard.", "success", "Copied to Clipboard");
    } catch(e) {
        showNotification("Could not access clipboard.", "error", "Copy Failed");
    }
}

// API Trigger: Launch Red Team Attacks
async function launchAttack(attackType) {
    const targetPkg = document.getElementById("select-attack-pkg").value;
    const consoleBox = document.getElementById("console-output");
    
    if (!targetPkg) {
        showNotification("Please select a target package to simulate the attack on.", "error", "Target Missing");
        return;
    }
    
    // Read parametric control inputs
    const replayDelay = parseInt(document.getElementById("input-replay-delay").value);
    const forkNodeId = document.getElementById("select-fork-node").value;
    const gpsOffset = parseFloat(document.getElementById("input-gps-offset").value);
    
    let spoofLat = 40.7128;
    let spoofLon = -74.0060;
    
    if (attackType === "gps_forgery") {
        // Fetch current shipment position to apply custom GPS offset values
        const history = await fetchCombinedHistory(targetPkg);
        if (history.length > 0) {
            const lastStep = history[history.length - 1];
            spoofLat = lastStep.location.lat + gpsOffset;
            spoofLon = lastStep.location.lon + gpsOffset;
        }
    }
    
    consoleBox.innerText = `Launching ${attackType.toUpperCase()} attack on package ${targetPkg}...\n`;
    
    try {
        const inferredRoute = await inferRouteForPackage(targetPkg);
        const url = `${API_URL}/simulate/attack?pkg_id=${targetPkg}&attack_type=${attackType}&route_name=${inferredRoute}&step_index=1&replay_delay=${replayDelay}&fork_node_id=${forkNodeId}&spoof_lat=${spoofLat}&spoof_lon=${spoofLon}`;
        const response = await fetch(url, {
            method: "POST"
        });
        
        const data = await response.json();
        
        if (response.ok) {
            consoleBox.innerText += `\n[ATTACK STATUS]: ${data.status.toUpperCase()}\n`;
            consoleBox.innerText += `[DETAIL]: ${data.detail}\n`;
            if (data.txs) {
                consoleBox.innerText += `[INJECTED TXS]: ${JSON.stringify(data.txs, null, 2)}\n`;
            }
            if (data.tx_id) {
                consoleBox.innerText += `[INJECTED TX]: ${data.tx_id}\n`;
            }
            consoleBox.innerText += `\nMonitor mempool or trigger mining to view consensus reaction.`;
            
            showSecurityVisualModal(attackType, data.status);
        } else {
            consoleBox.innerText += `\n[ERROR]: ${data.detail || 'Attack execution failed.'}`;
            showNotification(`The simulator rejected the attack attempt: ${data.detail}`, "error", "Simulation Error");
        }
        
        await syncLedgerData();
        
    } catch(e) {
        consoleBox.innerText += `\n[ERROR]: Failed to connect to backend endpoint.`;
        showNotification("API connection error occurred while launching attack.", "error", "Connection Failed");
    }
}

function showNotification(message, type = "success", title = "Notification") {
    const modal = document.getElementById("custom-modal");
    const iconEl = document.getElementById("modal-icon");
    const titleEl = document.getElementById("modal-title");
    const msgEl = document.getElementById("modal-message");
    
    if (type === "success") {
        iconEl.innerText = "";
        titleEl.style.color = "var(--success-green)";
    } else if (type === "error") {
        iconEl.innerText = "";
        titleEl.style.color = "var(--danger-red)";
    } else {
        iconEl.innerText = "";
        titleEl.style.color = "var(--primary-blue)";
    }
    
    titleEl.innerText = title;
    msgEl.innerHTML = message;
    modal.classList.add("active");
}

async function resetLedger() {
    // Check if the ledger is already at 0 blocks (excluding Genesis) and 0 pending transactions
    const blocksCount = parseInt(document.getElementById("stat-blocks").innerText) || 0;
    const mempoolCount = parseInt(document.getElementById("stat-mempool").innerText) || 0;
    
    if (blocksCount <= 1 && mempoolCount === 0) {
        showNotification("Ledger database and simulated package indexes are already reset.", "info", "System Ready");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/reset-ledger`, {
            method: "POST"
        });
        
        if (response.ok) {
            showNotification("Ledger database and simulated package indexes have been reset successfully.", "success", "System Reset");
            
            // Clear package selector dropdowns and current route plots
            document.getElementById("select-active-pkg").value = "";
            document.getElementById("input-pkg-id").value = "PKG-DELIVERY-01";
            
            // Clear maps and route plots
            loadPackageVisuals("");
            clearDrawnRoute();
            stopAutoTransit();
            stopAutoMine();
            
            // Clean up memory pool HTML view instantly
            document.getElementById("mempool-count-label").innerText = "0 pending transaction(s)";
            const tableBody = document.querySelector("#mempool-table tbody");
            if (tableBody) {
                tableBody.innerHTML = `<tr><td colspan="6" class="center-text">Queue is empty.</td></tr>`;
            }
            
            // Clean up quarantine table HTML view instantly
            const quarantineTableBody = document.querySelector("#quarantine-table tbody");
            if (quarantineTableBody) {
                quarantineTableBody.innerHTML = `<tr><td colspan="6" class="center-text">No quarantined transactions.</td></tr>`;
            }
            
            // Reset security console log text
            const consoleBox = document.getElementById("console-output");
            if (consoleBox) {
                consoleBox.innerText = "Terminal ready. Launch an attack vector to monitor system logs...";
            }
            
            // Synchronize active datasets (updates blocks, stats indicators, registry stats)
            await syncLedgerData();
        } else {
            showNotification("Failed to reset ledger.", "error", "System Reset Error");
        }
    } catch (e) {
        showNotification("API Connection Error", "error", "Connection Failed");
    }
}

// Interactive Attack Explanation Visual Module
function explainAttack(attackType) {
    showSecurityVisualModal(attackType, "info");
}

// Render dynamic interactive HTML pipeline flowchart modal for security attacks
function showSecurityVisualModal(attackType, status) {
    const modal = document.getElementById("security-visual-modal");
    const badge = document.getElementById("security-modal-badge");
    const titleEl = document.getElementById("security-modal-title");
    const flowContainer = document.getElementById("security-visual-flow");
    
    // Status text and formatting
    badge.innerText = status.toUpperCase();
    badge.className = "attack-status-badge " + status.toLowerCase();
    
    let title = "";
    let mechanism = "";
    let context = "";
    let defense = "";
    let flowHtml = "";
    
    if (attackType === "replay") {
        title = "Beacon Replay Attack";
        mechanism = "An attacker intercepts a valid cryptographic location token from a legitimate beacon scan. Hours later, the attacker replays this token at a different checkpoint node to simulate false package progress.";
        context = "Used to cover up cargo theft by fabricating checkpoint check-ins or faking compliance metrics without visiting physical depots.";
        defense = "Each location attestation token contains a rolling cryptographic timestamp epoch signed by the local Beacon. The PoA Consensus Validator checks the timestamp against block limits (e.g., within 5 mins). Replays of old tokens fail consensus validation and the block is rejected.";
        
        flowHtml = `
            <div class="visual-pipeline">
                <div class="visual-node active">
                    <div class="visual-node-circle">B</div>
                    <div class="visual-node-label">Beacon 101</div>
                    <div class="visual-node-status">Signed Token</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse"></div>
                </div>
                <div class="visual-node compromised">
                    <div class="visual-node-circle">A</div>
                    <div class="visual-node-label">Attacker</div>
                    <div class="visual-node-status">Replays Token</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse malicious"></div>
                </div>
                <div class="visual-node ${status === 'blocked' ? 'secured' : 'active'}">
                    <div class="visual-node-circle">V</div>
                    <div class="visual-node-label">Validator</div>
                    <div class="visual-node-status">${status === 'blocked' ? 'REJECTED (Consensus)' : 'IN QUEUE'}</div>
                </div>
            </div>
        `;
    } else if (attackType === "fork") {
        title = "Double-Location Fork Attack";
        mechanism = "An attacker clones a package's RFID/NFC security tag identity. The cloned tag is scanned at two different physical location nodes simultaneously, trying to create multiple valid historical branches (forks).";
        context = "Used to introduce counterfeit goods into the supply chain (cloning genuine batch tags) or executing double-insurance payout frauds.";
        defense = "The PoA Validator audits parent block link hashes ('prev_proof_hash'). If two concurrent transactions share the exact same package parent hash, the validator immediately flags the fork and rejects the block.";
        
        flowHtml = `
            <div class="visual-pipeline">
                <div class="visual-node active">
                    <div class="visual-node-circle">P</div>
                    <div class="visual-node-label">Parent Scan</div>
                    <div class="visual-node-status">Hash 0xabc123</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse"></div>
                </div>
                <div class="visual-node compromised">
                    <div class="visual-node-circle">D</div>
                    <div class="visual-node-label">Double Scan</div>
                    <div class="visual-node-status">Fork Branch</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse malicious"></div>
                </div>
                <div class="visual-node ${status === 'blocked' ? 'secured' : 'active'}">
                    <div class="visual-node-circle">V</div>
                    <div class="visual-node-label">Validator</div>
                    <div class="visual-node-status">${status === 'blocked' ? 'REJECTED (Double-Spend)' : 'IN QUEUE'}</div>
                </div>
            </div>
        `;
    } else if (attackType === "invalid_signature") {
        title = "Signature Tampering";
        mechanism = "An attacker intercepts a scanned location transaction payload in transit and alters key values (like timestamp or location ID) before submitting it to the blockchain ledger API.";
        context = "Executed via Man-in-the-Middle (MitM) tools to alter provenance history to hide route deviation or fake quality conditions.";
        defense = "All location scan packets must be signed by the scanner node's RSA private key. The API Gateway Filter verifies the signature against the public key registry. Since tampering modifies the payload, signature verification fails immediately, and the transaction is BLOCKED.";
        
        flowHtml = `
            <div class="visual-pipeline">
                <div class="visual-node active">
                    <div class="visual-node-circle">S</div>
                    <div class="visual-node-label">Scanner Node</div>
                    <div class="visual-node-status">Signed Scan</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse"></div>
                </div>
                <div class="visual-node compromised">
                    <div class="visual-node-circle">T</div>
                    <div class="visual-node-label">Tamperer</div>
                    <div class="visual-node-status">Alters Payload</div>
                </div>
                <div class="visual-connector blocked">
                    <div class="packet-pulse malicious blocked-pulse"></div>
                </div>
                <div class="visual-node secured">
                    <div class="visual-node-circle">G</div>
                    <div class="visual-node-label">API Gateway</div>
                    <div class="visual-node-status">BLOCKED (Invalid Sig)</div>
                </div>
            </div>
        `;
    } else if (attackType === "gps_forgery") {
        title = "Location Coordinate Forgery";
        mechanism = "A compromised or malicious scanner node attempts to spoof coordinates (e.g. reporting it is at a target hub when it is actually elsewhere) when submitting location proofs.";
        context = "Logistics companies or drivers attempting to bypass strict contractual route schedules or fake SLA milestones.";
        defense = "Every location scan requires a cryptographic attestation token generated and signed by the localized hardware Beacon. The API gateway verifies the Beacon's signature against the reported GPS coords. If they do not match, the packet is instantly BLOCKED.";
        
        flowHtml = `
            <div class="visual-pipeline">
                <div class="visual-node active">
                    <div class="visual-node-circle">B</div>
                    <div class="visual-node-label">Local Beacon</div>
                    <div class="visual-node-status">Signed GPS</div>
                </div>
                <div class="visual-connector active">
                    <div class="packet-pulse"></div>
                </div>
                <div class="visual-node compromised">
                    <div class="visual-node-circle">F</div>
                    <div class="visual-node-label">Fake GPS Node</div>
                    <div class="visual-node-status">Altered GPS</div>
                </div>
                <div class="visual-connector blocked">
                    <div class="packet-pulse malicious blocked-pulse"></div>
                </div>
                <div class="visual-node secured">
                    <div class="visual-node-circle">G</div>
                    <div class="visual-node-label">API Gateway</div>
                    <div class="visual-node-status">BLOCKED (GPS Mismatch)</div>
                </div>
            </div>
        `;
    }
    
    titleEl.innerText = title;
    document.getElementById("security-modal-mechanism").innerText = mechanism;
    document.getElementById("security-modal-context").innerText = context;
    document.getElementById("security-modal-defense").innerText = defense;
    flowContainer.innerHTML = flowHtml;
    
    modal.classList.add("active");
}

async function showAttackBlockedModal(errorDetail) {
    const modal = document.getElementById("security-alert-modal");
    const container = document.getElementById("security-alert-body");
    
    // Default values
    let attackType = "Consensus Block Rejection";
    let explanation = "The Proof-of-Authority validator rejected the block due to a validation rules violation.";
    let targetPkg = "N/A";
    let nodeId = "N/A";
    let beaconId = "N/A";
    let locationName = "N/A";
    let discrepancyHtml = "";
    
    // Parse regex
    const regex = /Consensus Validation Block Rejected:\s+Tx Validation Failed for\s+([a-fA-F0-9]+):\s+(.*)/;
    const match = errorDetail.match(regex);
    
    if (match) {
        const txId = match[1];
        const txError = match[2];
        activeOffendingTxId = txId;
        
        // Fetch mempool to get offending transaction details
        try {
            const mempoolRes = await fetch(`${API_URL}/mempool`);
            if (mempoolRes.ok) {
                const mempool = await mempoolRes.json();
                const offendingTx = mempool.find(tx => tx.tx_id === txId);
                if (offendingTx) {
                    targetPkg = offendingTx.pkg_id;
                    nodeId = offendingTx.node_id;
                    beaconId = offendingTx.beacon_id;
                    locationName = `${offendingTx.location.lat.toFixed(4)}, ${offendingTx.location.lon.toFixed(4)}`;
                }
            }
        } catch(e) {
            console.error("Failed to query mempool:", e);
        }
        
        if (txError.includes("Provenance chain broken")) {
            attackType = "Double-Location Fork Attack";
            explanation = "The validator detected a duplicate transaction chain. Two location scans were submitted for the same package referencing the same previous ledger state, indicating the package tag was cloned and scanned at two places concurrently.";
            
            const forkRegex = /references prev_hash\s+'([a-fA-F0-9]+)',\s+but ledger expected\s+'([a-fA-F0-9]+)'/;
            const forkMatch = txError.match(forkRegex);
            if (forkMatch) {
                const receivedHash = forkMatch[1];
                const expectedHash = forkMatch[2];
                const formatHash = (h) => {
                    if (!h) return "None";
                    if (h === "0") return "0 (Genesis / Start Link)";
                    if (h.length <= 16) return h;
                    return `${h.slice(0, 10)}...${h.slice(-6)}`;
                };
                discrepancyHtml = `
                    <div class="discrepancy-card">
                        <div class="discrepancy-title">State Linkage Mismatch (Double Spend Check):</div>
                        <div class="discrepancy-row">
                            <div>
                                <span class="row-label">Expected Parent Hash (Legitimate Path)</span>
                                <pre class="hash-box green-hash" title="${expectedHash}">${formatHash(expectedHash)}</pre>
                            </div>
                            <div class="versus-divider">VS</div>
                            <div>
                                <span class="row-label">Received Parent Hash (Fork Attack)</span>
                                <pre class="hash-box red-hash" title="${receivedHash}">${formatHash(receivedHash)}</pre>
                            </div>
                        </div>
                    </div>
                `;
            }
        } else if (txError.includes("expired") || txError.includes("Timestamp")) {
            attackType = "Beacon Replay Attack";
            explanation = "The attestation token's timestamp was older than the allowed 300-second (5-minute) freshness threshold. This indicates an attacker intercepted a past location attestation token and re-submitted it later to spoof history.";
            
            const replayRegex = /Timestamp\s+(\d+)\s+is older/;
            const replayMatch = txError.match(replayRegex);
            if (replayMatch) {
                const txTime = parseInt(replayMatch[1]);
                const currTime = Math.round(Date.now() / 1000);
                const age = currTime - txTime;
                
                discrepancyHtml = `
                    <div class="discrepancy-card">
                        <div class="discrepancy-title">Temporal Freshness Threshold Exceeded:</div>
                        <div class="discrepancy-row">
                            <div>
                                <span class="row-label">Allowed Limit</span>
                                <pre class="hash-box green-hash">Max 300s Age</pre>
                            </div>
                            <div class="versus-divider">VS</div>
                            <div>
                                <span class="row-label">Actual Token Age</span>
                                <pre class="hash-box red-hash">${age}s Elapsed</pre>
                            </div>
                        </div>
                    </div>
                `;
            }
        } else if (txError.includes("Invalid Node signature")) {
            attackType = "Node Signature Tampering";
            explanation = "The validator detected that the logistics node's cryptographic signature is invalid. The scanned location payload was altered or corrupted in transit after signature generation.";
            
            discrepancyHtml = `
                <div class="discrepancy-card">
                    <div class="discrepancy-title">Signature Validation:</div>
                    <div class="discrepancy-row">
                        <div>
                            <span class="row-label">Expected Cryptographic Value</span>
                            <pre class="hash-box green-hash">Valid Node RSA Signature</pre>
                        </div>
                        <div class="versus-divider">VS</div>
                        <div>
                            <span class="row-label">Received Value</span>
                            <pre class="hash-box red-hash">Altered/Corrupted Payload</pre>
                        </div>
                    </div>
                </div>
            `;
        } else if (txError.includes("Invalid Beacon signature")) {
            attackType = "Location Coordinate Forgery";
            explanation = "The validator detected an invalid location beacon signature. This indicates that the coordinates in the transaction were modified after the beacon signed them, or a forged beacon identity was used.";
            
            discrepancyHtml = `
                <div class="discrepancy-card">
                    <div class="discrepancy-title">Beacon Signature Match:</div>
                    <div class="discrepancy-row">
                        <div>
                            <span class="row-label">Expected GPS Attestation</span>
                            <pre class="hash-box green-hash">Signed Coordinates Match</pre>
                        </div>
                        <div class="versus-divider">VS</div>
                        <div>
                            <span class="row-label">Received GPS Attestation</span>
                            <pre class="hash-box red-hash">Modified Coordinates</pre>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    // Inject content
    container.innerHTML = `
        <div class="security-alert-container">
            <div class="security-alert-msg">
                <strong>Raw API Rejection Reason:</strong><br/>
                ${errorDetail}
            </div>
            
            <div class="alert-details-grid">
                <div class="alert-detail-item">
                    <span class="detail-label">Blocked Attack Vector</span>
                    <span class="detail-value highlight-red">${attackType}</span>
                </div>
                <div class="alert-detail-item">
                    <span class="detail-label">Target Package</span>
                    <span class="detail-value">${targetPkg}</span>
                </div>
                <div class="alert-detail-item">
                    <span class="detail-label">Target Node</span>
                    <span class="detail-value">${nodeId}</span>
                </div>
                <div class="alert-detail-item">
                    <span class="detail-label">Scanned Location</span>
                    <span class="detail-value">${locationName}</span>
                </div>
            </div>
            
            <div class="alert-explanation">
                <h4>Analysis & Defense Mechanism</h4>
                <p>${explanation}</p>
            </div>
            
            ${discrepancyHtml}
            
            <div class="security-footer-note">
                Consensus validation complete. The block was rejected, preventing ledger corruption.
            </div>
        </div>
    `;
    
    // Trigger Lucide icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    modal.classList.add("active");
}

async function loadQuarantineList() {
    const tableBody = document.querySelector("#quarantine-table tbody");
    if (!tableBody) return;
    
    try {
        const response = await fetch(`${API_URL}/quarantine`);
        if (response.ok) {
            const quarantined = await response.json();
            
            if (quarantined.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="6" class="center-text">No quarantined transactions.</td></tr>`;
                return;
            }
            
            tableBody.innerHTML = "";
            quarantined.forEach(tx => {
                const tr = document.createElement("tr");
                tr.style.background = "rgba(239, 68, 68, 0.04)";
                tr.style.borderLeft = "4px solid var(--danger-red)";
                tr.innerHTML = `
                    <td>${tx.pkg_id}</td>
                    <td>${tx.node_id}</td>
                    <td>${tx.beacon_id}</td>
                    <td>${tx.location.lat.toFixed(4)}, ${tx.location.lon.toFixed(4)}</td>
                    <td>${new Date(tx.quarantine_time * 1000).toLocaleTimeString()}</td>
                    <td>
                        <div style="display: flex; flex-direction: column; gap: 2px;">
                            <span style="color: var(--danger-red); font-weight: 700;">⚠️ ${tx.threat_type}</span>
                            <span style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.2;">${tx.reason}</span>
                        </div>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        }
    } catch(e) {
        console.error("Failed to load quarantine list:", e);
    }
}

/* Custom Route Drawing Helpers */
function toggleDrawMode() {
    isDrawMode = !isDrawMode;
    const btn = document.getElementById("btn-draw-mode");
    if (isDrawMode) {
        btn.innerText = "Draw Mode: ON";
        btn.classList.add("primary");
        btn.classList.remove("secondary");
        showNotification("Draw Mode Active. Click points on the Leaflet Map to place checkpoints.", "info", "Draw Mode Enabled");
    } else {
        btn.innerText = "Draw Mode: OFF";
        btn.classList.remove("primary");
        btn.classList.add("secondary");
    }
}

function clearDrawnRoute() {
    drawnCheckpoints = [];
    drawnMarkers.forEach(m => map.removeLayer(m));
    drawnMarkers = [];
    if (drawnPolyline) {
        map.removeLayer(drawnPolyline);
        drawnPolyline = null;
    }
    document.getElementById("btn-save-custom-route").disabled = true;
}

function addDrawnCheckpoint(lat, lon) {
    const stepNum = drawnCheckpoints.length + 1;
    const checkpointName = prompt(`Enter name for Checkpoint #${stepNum}:`, `Checkpoint ${stepNum}`);
    if (!checkpointName) return;
    
    const id = (2000 + stepNum).toString();
    const checkpoint = { id, name: checkpointName, lat, lon };
    drawnCheckpoints.push(checkpoint);
    
    const marker = L.circleMarker([lat, lon], {
        radius: 8,
        fillColor: "#A78BFA",
        color: "#FFFFFF",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
    }).addTo(map);
    
    marker.bindPopup(`<strong>Checkpoint #${stepNum}</strong><br/>${checkpointName}`);
    drawnMarkers.push(marker);
    
    const latLngs = drawnCheckpoints.map(c => [c.lat, c.lon]);
    if (drawnPolyline) {
        drawnPolyline.setLatLngs(latLngs);
    } else {
        drawnPolyline = L.polyline(latLngs, {
            color: "#A78BFA",
            weight: 3,
            dashArray: "4, 6",
            opacity: 0.8
        }).addTo(map);
    }
    
    if (drawnCheckpoints.length >= 2) {
        document.getElementById("btn-save-custom-route").disabled = false;
    }
}

async function saveCustomRoute() {
    const routeNameInput = document.getElementById("input-custom-route-name").value.trim();
    if (!routeNameInput) {
        showNotification("Please enter a custom route name.", "error", "Name Missing");
        return;
    }
    
    const routeSlug = routeNameInput.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    
    try {
        const response = await fetch(`${API_URL}/routes`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ route_name: routeSlug, steps: drawnCheckpoints })
        });
        
        if (response.ok) {
            ROUTE_TEMPLATES[routeSlug] = [...drawnCheckpoints];
            populateRouteSelect();
            document.getElementById("select-route").value = routeSlug;
            
            showNotification(`Custom route "${routeNameInput}" registered successfully!`, "success", "Route Registered");
            
            if (isDrawMode) toggleDrawMode();
            clearDrawnRoute();
        } else {
            const err = await response.json();
            showNotification(`Failed to save route: ${err.detail}`, "error", "Registration Error");
        }
    } catch (e) {
        showNotification("API connection error occurred while saving route.", "error", "Connection Failed");
    }
}

function populateRouteSelect() {
    const select = document.getElementById("select-route");
    if (!select) return;
    const currentVal = select.value;
    
    select.innerHTML = "";
    Object.keys(ROUTE_TEMPLATES).forEach(key => {
        let displayName = key.replace(/_/g, ' ').toUpperCase();
        if (key === "standard_delivery") displayName = "Warehouse ──► Delivery Truck ──► Retail Store";
        else if (key === "electronics_import") displayName = "Electronics Import (Shenzhen ──► NYC)";
        else if (key === "pharmaceuticals_cold_chain") displayName = "Pharma Cold Chain (Munich ──► Miami)";
        
        select.innerHTML += `<option value="${key}">${displayName}</option>`;
    });
    
    if (ROUTE_TEMPLATES[currentVal]) {
        select.value = currentVal;
    }
}

/* Automation Controllers & Background Loops */
async function autoTransitStep() {
    const select = document.getElementById("select-active-pkg");
    const activePkg = select.value;
    if (!activePkg) {
        stopAutoTransit();
        return;
    }
    
    const inferredRoute = await inferRouteForPackage(activePkg);
    const history = await fetchCombinedHistory(activePkg);
    const maxSteps = ROUTE_TEMPLATES[inferredRoute].length;
    
    if (history.length >= maxSteps) {
        stopAutoTransit();
        showNotification(`Package ${activePkg} has completed the route. Auto-Transit stopped.`, "success", "Route Completed");
        return;
    }
    
    await advanceShipment();
}

function stopAutoTransit() {
    const toggle = document.getElementById("toggle-auto-transit");
    if (toggle) toggle.checked = false;
    if (autoTransitInterval) {
        clearInterval(autoTransitInterval);
        autoTransitInterval = null;
    }
}

async function autoMineStep() {
    try {
        const res = await fetch(`${API_URL}/mempool`);
        if (res.ok) {
            const mempool = await res.json();
            if (mempool.length > 0) {
                await mineBlocks();
            }
        }
    } catch(e) {}
}

function stopAutoMine() {
    const toggle = document.getElementById("toggle-auto-mine");
    if (toggle) toggle.checked = false;
    if (autoMineInterval) {
        clearInterval(autoMineInterval);
        autoMineInterval = null;
    }
}

/* Dynamic Fork node options helper */
async function populateForkNodes(pkgId) {
    const select = document.getElementById("select-fork-node");
    if (!select) return;
    
    let routeName = "standard_delivery";
    if (pkgId) {
        routeName = await inferRouteForPackage(pkgId);
    }
    
    const steps = ROUTE_TEMPLATES[routeName];
    if (!steps) return;
    
    select.innerHTML = "";
    steps.forEach(step => {
        const nodeId = `NODE-${step.id}`;
        select.innerHTML += `<option value="${nodeId}">${nodeId} (${step.name})</option>`;
    });
    
    if (!steps.some(step => `NODE-${step.id}` === "NODE-304")) {
        select.innerHTML += `<option value="NODE-304">NODE-304 (Dallas Logistics Hub - Default Attack)</option>`;
    }
}
