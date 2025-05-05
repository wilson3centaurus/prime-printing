/**
 * PREVIEW SYSTEM CORE FUNCTIONALITY
 * Handles payment processing and printing for all document types
 */

// Configuration
const config = {
    costPerPage: 0.10,
    pollInterval: 5000 // 5 seconds
};

// Global state
let state = {
    paymentReference: null,
    pollUrl: null,
    pollTimer: null,
    totalPages: 1 // Default for non-PDF files
};

/**
 * Initialize print modal and payment system
 */
function initPrintSystem() {
    // Modal elements
    const printModal = document.getElementById('print-modal');
    const printForm = document.getElementById('printForm');
    
    if (!printModal || !printForm) return; // Skip if no modal exists
    
    // Set up event listeners
    document.getElementById('print-btn')?.addEventListener('click', () => {
        printModal.classList.remove('hidden');
        printModal.classList.add('flex');
    });

    document.getElementById('close-modal')?.addEventListener('click', () => {
        printModal.classList.add('hidden');
        printModal.classList.remove('flex');
    });

    printForm.addEventListener('submit', handlePrintSubmit);
}

/**
 * Handle print form submission
 */
async function handlePrintSubmit(e) {
    e.preventDefault();
    
    const formData = {
        copies: parseInt(document.getElementById('copiesInput').value) || 1,
        pages: document.getElementById('pagesInput').value.trim().toLowerCase(),
        orientation: document.getElementById('printForm').orientation.value,
        ecocash: document.getElementById('printForm').ecocash.value.trim(),
        printpass: document.getElementById('printForm').printpass.value.trim(),
        filename: document.getElementById('filename').value,
        filepath: document.getElementById('filepath').value,
        totalPages: state.totalPages
    };

    // Validate EcoCash number
    if (!/^07[78]\d{7}$/.test(formData.ecocash)) {
        showError('Please enter a valid Zimbabwean EcoCash number (077/078 followed by 7 digits)');
        return;
    }

    showLoadingState();

    try {
        const response = await fetch('/process-print', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || "Payment processing failed");
        }

        state.paymentReference = result.reference;
        state.pollUrl = result.poll_url;
        
        showPaymentInstructions(result.instructions);
        startPolling();

    } catch (error) {
        showError(error.message);
    }
}

/**
 * Start polling for payment status
 */
function startPolling() {
    if (state.pollTimer) clearTimeout(state.pollTimer);
    
    state.pollTimer = setTimeout(() => {
        checkPaymentStatus();
    }, config.pollInterval);
}

/**
 * Check current payment status
 */
async function checkPaymentStatus() {
    if (!state.pollUrl) {
        showError("Payment reference missing");
        return;
    }

    try {
        updateStatusText('Checking payment status...');
        
        const response = await fetch('/check-payment-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                poll_url: state.pollUrl, 
                reference: state.paymentReference 
            })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || "Status check failed");
        }

        handlePaymentResponse(result);

    } catch (error) {
        showError(error.message);
    }
}

/**
 * Handle payment status response
 */
function handlePaymentResponse(result) {
    const status = (result.status || '').toLowerCase();
    
    if (status.includes('paid')) {
        showPaymentSuccess(result);
    } 
    else if (status.includes('cancel') || status.includes('failed')) {
        showError("Payment was cancelled");
    }
    else if (status.includes('error') || status.includes('invalid')) {
        showError("Payment failed (wrong PIN or insufficient funds)");
    }
    else {
        updateStatusText('Waiting for payment confirmation...');
        startPolling();
    }
}

/**
 * UI Helper Functions
 */
function showLoadingState() {
    document.getElementById('printForm').style.display = 'none';
    document.getElementById('statusBox').classList.remove('hidden');
    updateStatusText('Processing your payment request...');
    toggleIcons('spinner');
}

function showPaymentInstructions(instructions) {
    const instructionsEl = document.getElementById('paymentInstructions');
    if (instructions && instructionsEl) {
        instructionsEl.classList.remove('hidden');
        document.getElementById('instructionsText').textContent = instructions;
    }
}

function showPaymentSuccess(result) {
    clearTimeout(state.pollTimer);
    toggleIcons('success');
    updateStatusText(`
        <div class="text-green-600 font-bold mb-2">Payment Successful!</div>
        <div class="text-gray-600">Your document is being printed.</div>
        <div class="text-gray-600">Reference: ${state.paymentReference}</div>
    `);
}

function showError(message) {
    clearTimeout(state.pollTimer);
    toggleIcons('error');
    
    let userMessage = message;
    if (message.includes('cancel')) userMessage = "Payment was cancelled";
    if (message.includes('wrong pin')) userMessage = "Incorrect PIN entered";
    if (message.includes('insufficient')) userMessage = "Insufficient funds";
    
    updateStatusText(`
        <div class="text-red-600 font-bold mb-2">Error</div>
        <div>${userMessage}</div>
    `);
}

function toggleIcons(iconToShow) {
    ['spinner', 'success', 'error'].forEach(icon => {
        const el = document.getElementById(`${icon}Icon`);
        if (el) el.classList.toggle('hidden', icon !== iconToShow);
    });
}

function updateStatusText(html) {
    const el = document.getElementById('statusText');
    if (el) el.innerHTML = html;
}

/**
 * Initialize when DOM is loaded
 */
document.addEventListener('DOMContentLoaded', () => {
    initPrintSystem();
    
    // Set total pages for non-PDF files
    const pageCountEl = document.getElementById('totalPages');
    if (pageCountEl && pageCountEl.textContent === '0') {
        pageCountEl.textContent = '1';
        state.totalPages = 1;
    }
});