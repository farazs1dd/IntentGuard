// IntentGuard Unified Dashboard JavaScript

let ws = null;
let testResults = [];
let totalTests = 0;
let completedTests = 0;
let currentMode = 'benchmark';

// Mode Switching
function switchMode(mode) {
    currentMode = mode;

    // Update tabs
    document.querySelectorAll('.mode-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');

    // Update content
    document.querySelectorAll('.mode-content').forEach(content => {
        content.classList.remove('active');
    });

    if (mode === 'benchmark') {
        document.getElementById('benchmarkMode').classList.add('active');
    } else if (mode === 'custom') {
        document.getElementById('customMode').classList.add('active');
    }
}

// Quick Scenario Templates
const quickScenarios = {
    banking: {
        prompt: 'Investigate transaction #84721 and hold if fraudulent',
        tools: 'read_transaction, inspect_account_history, assess_fraud_risk, hold_transaction',
        resources: '84721'
    },
    retail: {
        prompt: 'Process order #ORD-4472 and ship to customer',
        tools: 'get_order_details, verify_payment, check_inventory, ship_order',
        resources: 'ORD-4472'
    },
    airline: {
        prompt: 'Cancel booking #BK-2847 and refund passenger',
        tools: 'get_booking, check_cancellation_policy, cancel_booking, process_refund',
        resources: 'BK-2847'
    }
};

function loadQuickScenario(type) {
    const scenario = quickScenarios[type];
    document.getElementById('customPrompt').value = scenario.prompt;
    document.getElementById('customTools').value = scenario.tools;
    document.getElementById('customResources').value = scenario.resources;
}

// Custom Scenario Analysis
function analyzeCustomScenario() {
    const prompt = document.getElementById('customPrompt').value.trim();
    const tools = document.getElementById('customTools').value.split(',').map(t => t.trim()).filter(t => t);
    const resources = document.getElementById('customResources').value.split(',').map(r => r.trim()).filter(r => r);

    if (!prompt || tools.length === 0) {
        alert('Please provide a user prompt and at least one authorized tool');
        return;
    }

    // Create mock contract
    const contract = {
        authorized_tools: tools,
        resource_scope: {
            transaction_ids: resources,
            account_ids: [],
            allowed_scope_expansion: false
        },
        constraints: {}
    };

    // Show analysis
    const resultsDiv = document.getElementById('customResults');
    const contentDiv = document.getElementById('customResultsContent');

    let html = `
        <div class="test-item">
            <div class="test-meta">
                <div class="test-id">CUSTOM-SCENARIO</div>
                <div class="test-badges">
                    <span class="test-badge" style="background: var(--accent-primary);">LIVE ANALYSIS</span>
                </div>
            </div>

            <div class="test-intent">"${prompt}"</div>

            <div class="contract-details">
                <div class="contract-header">📋 Your Intent Contract</div>

                <div class="contract-section">
                    <div class="contract-label">✓ Authorized Tools</div>
                    <div class="tool-list">
                        ${tools.map(tool => `<span class="tool-tag authorized">${tool}</span>`).join('')}
                    </div>
                </div>

                <div class="contract-section">
                    <div class="contract-label">🎯 Authorized Resources</div>
                    <div class="contract-value">${resources.join(', ') || 'None specified'}</div>
                </div>
            </div>

            <div style="margin-top: 24px; padding: 20px; background: rgba(99, 102, 241, 0.1); border-radius: 8px; border: 1px solid var(--accent-primary);">
                <div style="font-weight: 700; color: var(--accent-primary); margin-bottom: 12px;">
                    🔍 How IntentGuard Would Protect This
                </div>
                <div style="font-size: 14px; line-height: 1.8; color: var(--text-secondary);">
                    <strong style="color: var(--text-primary);">✅ Would ALLOW:</strong><br>
                    Any tool call using the ${tools.length} authorized tools: <code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 3px;">${tools.join(', ')}</code>
                    ${resources.length > 0 ? `<br>Operating on resources: <code style="background: var(--bg-tertiary); padding: 2px 6px; border-radius: 3px;">${resources.join(', ')}</code>` : ''}
                    <br><br>

                    <strong style="color: var(--text-primary);">🚫 Would BLOCK:</strong><br>
                    • Any tool <strong>NOT</strong> in the authorized list (deviation: 100/100)<br>
                    ${resources.length > 0 ? `• Any resource ID <strong>NOT</strong> in [${resources.join(', ')}] (deviation: 100/100)<br>` : ''}
                    • Critical prerequisite violations (e.g., approve_loan without run_credit_check)<br>
                    • Duplicate calls to single-use tools (e.g., process_refund called twice)<br>
                    • Account-level actions when only transaction-level authorized<br>
                    <br>

                    <strong style="color: var(--text-primary);">⚠️ Would REQUIRE CONFIRMATION:</strong><br>
                    • Medium-risk actions (deviation: 40-69/100)<br>
                    • Resource scope expansions<br>
                    • Constraint violations
                </div>
            </div>

            <div style="margin-top: 20px; padding: 16px; background: var(--bg-tertiary); border-radius: 8px; border: 1px solid var(--border);">
                <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
                    <strong style="color: var(--text-primary);">💡 Tip:</strong> To see real attack detection,
                    run the full benchmark suite with pre-built test scenarios that demonstrate actual attacks
                    being blocked. Click "Full Benchmark Suite" tab above.
                </div>
            </div>
        </div>
    `;

    contentDiv.innerHTML = html;
    resultsDiv.style.display = 'block';
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        document.getElementById('wsStatus').classList.remove('disconnected');
        document.getElementById('wsStatusText').textContent = 'Connected';
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        document.getElementById('wsStatus').classList.add('disconnected');
        document.getElementById('wsStatusText').textContent = 'Disconnected';
        setTimeout(connectWebSocket, 3000);
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWebSocketMessage(message) {
    const { type, data } = message;

    switch (type) {
        case 'test_suite_started':
            totalTests = data.total_tests;
            completedTests = 0;
            testResults = [];
            document.getElementById('testList').innerHTML = '';
            updateMetrics();
            break;

        case 'test_started':
            addTestItem(data, 'running');
            break;

        case 'test_completed':
            updateTestItem(data);
            completedTests++;
            updateProgress();
            updateMetrics();
            break;

        case 'test_suite_completed':
            document.getElementById('runBtn').disabled = false;
            document.getElementById('runBtn').innerHTML = 'Run Tests';
            break;
    }
}

function addTestItem(data, status) {
    const testList = document.getElementById('testList');
    const item = document.createElement('div');
    item.className = `test-item ${status}`;
    item.id = `test-${data.test_id}`;

    const statusBadge = status === 'running'
        ? '<span class="test-badge badge-running">RUNNING...</span>'
        : '';

    item.innerHTML = `
        <div class="test-meta">
            <div class="test-id">${data.test_id}</div>
            <div class="test-badges">${statusBadge}</div>
        </div>
        <div class="test-intent">"${data.user_intent}"</div>
        <div class="test-details">
            <strong>Domain:</strong> ${data.domain.toUpperCase()} |
            <strong>Pattern:</strong> ${data.attack_pattern.replace(/_/g, ' ').toUpperCase()}
        </div>
    `;

    testList.appendChild(item);
}

function updateTestItem(data) {
    const item = document.getElementById(`test-${data.test_id}`);
    if (!item) return;

    const result = data.result;
    const status = result.detected ? 'detected' : 'missed';

    item.className = `test-item ${status}`;

    const badge = result.detected
        ? `<span class="test-badge badge-detected">✓ DETECTED</span>`
        : `<span class="test-badge badge-missed">✗ MISSED</span>`;

    let deviationBadge = '';
    if (result.deviation_score !== null) {
        const scoreClass = result.deviation_score >= 70 ? 'high' :
                         result.deviation_score >= 40 ? 'medium' : 'low';
        deviationBadge = `<span class="deviation-score ${scoreClass}">${result.deviation_score}/100</span>`;
    }

    const contract = data.intent_contract || {};
    let contractHtml = '<div class="contract-details">';
    contractHtml += '<div class="contract-header">📋 Intent Contract</div>';

    if (contract.authorized_tools && contract.authorized_tools.length > 0) {
        contractHtml += '<div class="contract-section">';
        contractHtml += '<div class="contract-label">✓ Authorized Tools</div>';
        contractHtml += '<div class="tool-list">';
        contract.authorized_tools.forEach(tool => {
            contractHtml += `<span class="tool-tag authorized">${tool}</span>`;
        });
        contractHtml += '</div></div>';
    }

    if (contract.resource_scope && contract.resource_scope.transaction_ids) {
        contractHtml += '<div class="contract-section">';
        contractHtml += '<div class="contract-label">🎯 Authorized Resources</div>';
        contractHtml += `<div class="contract-value">${contract.resource_scope.transaction_ids.join(', ') || 'None'}</div>`;
        contractHtml += '</div>';
    }

    if (contract.constraints && Object.keys(contract.constraints).length > 0) {
        contractHtml += '<div class="contract-section">';
        contractHtml += '<div class="contract-label">⚠️ Constraints</div>';
        contractHtml += '<div class="contract-value">';
        Object.entries(contract.constraints).forEach(([key, value]) => {
            contractHtml += `${key}: ${value}<br>`;
        });
        contractHtml += '</div></div>';
    }

    contractHtml += '</div>';

    const authorizedTools = contract.authorized_tools || [];
    let attackSeq = '<div class="attack-sequence">';
    attackSeq += '<div class="sequence-header">🔍 Attack Sequence vs Contract</div>';
    data.attack_sequence.forEach((step, idx) => {
        const isBlocked = result.blocked_at_stage && idx + 1 === result.blocked_at_stage;
        const isAuthorized = authorizedTools.includes(step.tool);
        const stepClass = isBlocked ? 'blocked' : 'allowed';
        const icon = isBlocked ? '🚫' : (isAuthorized ? '✅' : '⚠️');

        attackSeq += `<div class="sequence-step ${stepClass}">
            <span class="step-icon">${icon}</span>
            <span>${step.step}.</span>
            <span class="step-tool">${step.tool}</span>
            <span style="color: var(--text-secondary);">(${Object.keys(step.params).join(', ')})</span>
            ${!isAuthorized && !isBlocked ? '<span class="step-warning">UNAUTHORIZED</span>' : ''}
            ${isBlocked ? '<span class="step-blocked">BLOCKED</span>' : ''}
        </div>`;
    });
    attackSeq += '</div>';

    let violationHtml = '';
    if (result.detected && result.block_reason) {
        violationHtml = `
            <div class="violation-box">
                <div class="violation-header">🚫 Why This Was Blocked</div>
                <div class="violation-reason">${result.block_reason}</div>
            </div>
        `;
    }

    item.innerHTML = `
        <div class="test-meta">
            <div class="test-id">${data.test_id}</div>
            <div class="test-badges">
                ${badge}
                ${deviationBadge}
            </div>
        </div>
        <div class="test-intent">"${data.user_intent}"</div>
        <div class="test-details">
            <strong>Domain:</strong> ${data.domain.toUpperCase()} |
            <strong>Pattern:</strong> ${data.attack_pattern.replace(/_/g, ' ').toUpperCase()} |
            <strong>Severity:</strong> ${data.severity.toUpperCase()}
        </div>
        <div class="test-details" style="margin-top: 8px;">
            <strong>Attack:</strong> ${data.attack_description}
        </div>
        <div class="test-details">
            <strong>Impact:</strong> ${data.business_impact}
        </div>
        ${contractHtml}
        ${attackSeq}
        ${violationHtml}
    `;

    testResults.push(result);
}

function updateProgress() {
    if (totalTests === 0) return;
    const percent = (completedTests / totalTests) * 100;
    document.getElementById('progressBar').style.width = `${percent}%`;
}

function updateMetrics() {
    const detected = testResults.filter(r => r.detected).length;
    const missed = testResults.length - detected;
    const detectionRate = testResults.length > 0
        ? (detected / testResults.length * 100).toFixed(1)
        : 0;

    const deviationScores = testResults
        .map(r => r.deviation_score)
        .filter(s => s !== null);
    const avgDeviation = deviationScores.length > 0
        ? (deviationScores.reduce((a, b) => a + b, 0) / deviationScores.length).toFixed(1)
        : '-';

    document.getElementById('totalTests').textContent = totalTests || testResults.length;
    document.getElementById('detectedCount').textContent = detected;
    document.getElementById('missedCount').textContent = missed;
    document.getElementById('detectionRate').textContent = `${detectionRate}%`;
    document.getElementById('avgDeviation').textContent = avgDeviation !== '-' ? `${avgDeviation}/100` : '-';
}

async function runTests() {
    const domain = document.getElementById('domainSelect').value;
    const runBtn = document.getElementById('runBtn');

    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="loading"></span> Running...';

    try {
        const response = await fetch('/api/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                domain: domain || null,
                verbose: true
            })
        });

        const result = await response.json();
        console.log('Test execution started:', result);
    } catch (error) {
        console.error('Error running tests:', error);
        runBtn.disabled = false;
        runBtn.innerHTML = 'Run Tests';
    }
}

function clearResults() {
    testResults = [];
    totalTests = 0;
    completedTests = 0;
    document.getElementById('testList').innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">🚀</div>
            <p>Click "Run Tests" to start the security benchmark</p>
        </div>
    `;
    document.getElementById('progressBar').style.width = '0%';
    updateMetrics();
}

// Initialize
connectWebSocket();

setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
    }
}, 30000);
