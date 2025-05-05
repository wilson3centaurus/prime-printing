// File type icons mapping
const FILE_ICONS = {
    pdf: 'far fa-file-pdf',
    docx: 'far fa-file-word',
    jpg: 'far fa-file-image',
    jpeg: 'far fa-file-image',
    png: 'far fa-file-image'
};

// Supported file types
const SUPPORTED_TYPES = ['pdf', 'docx', 'jpg', 'jpeg', 'png'];

// DOM elements
const fileList = document.getElementById('fileList');
const usbStatus = document.getElementById('usbStatus');
const refreshBtn = document.getElementById('refreshBtn');

// Main function to load files
async function loadFiles() {
    try {
        const response = await fetch('/files');
        const files = await response.json();
        
        // Filter only supported files
        const supportedFiles = files.filter(file => 
            SUPPORTED_TYPES.includes(file.type.toLowerCase())
        );
        
        updateUSBStatus(supportedFiles.length > 0);
        renderFiles(supportedFiles);
    } catch (error) {
        console.error("Error loading files:", error);
        usbStatus.innerHTML = '<span class="disconnected">Connecting....</span>';
        fileList.innerHTML = '<tr><td colspan="4" class="no-files">Please wait patiently while your usb is being connected!</td></tr>';
    }
}

// Update USB status display
// Update USB status display and handle redirection
function updateUSBStatus(connected) {
    if (connected) {
        usbStatus.innerHTML = '<span class="connected">💾 USB Connected</span>';
        // Only redirect if we're not already on the USB page
        if (!window.location.pathname.endsWith('usb')) {
            window.location.href = 'usb';
        }
    } else {
        usbStatus.innerHTML = '<span class="disconnected">Connecting.......</span>';
        // Only redirect to dashboard if we're on the USB page
        if (window.location.pathname.endsWith('usb')) {
            window.location.href = '/';
        }
    }
}

// Render files in the table
function renderFiles(files) {
    if (files.length === 0) {
        fileList.innerHTML = '<tr><td colspan="4" class="no-files">No supported files found</td></tr>';
        return;
    }
    
    fileList.innerHTML = files.map(file => `
        <tr>
            <td>
                <i class="${FILE_ICONS[file.type] || 'far fa-file'} file-icon"></i>
                ${file.name}
            </td>
            <td>${file.type.toUpperCase()}</td>
            <!--<td>${file.pages || '--'}</td>-->

            <td>
                <button class="file-btn" onclick="previewFile('${escapePath(file.path)}')">
                    <i class="fas fa-eye"></i> Open/Print
                </button>
            </td>
        </tr>
    `).join('');
}

// Estimate page count (simplified)
function estimatePageCount(file) {
    if (file.type === 'pdf') return 'Multiple';
    if (file.type === 'docx') return '--';
    return '1'; // For images
}

// Escape file path for JS
function escapePath(path) {
    return path.replace(/'/g, "\\'");
}

// Preview file function
function previewFile(filepath) {
    const encoded = btoa(unescape(encodeURIComponent(filepath)));
    window.location.href = `/preview/${encoded}`;
}

// Initialize and set up auto-refresh
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    loadFiles();
    
    // Manual refresh button
    refreshBtn.addEventListener('click', loadFiles);
    
    // Auto-refresh every 1 seconds
    setInterval(loadFiles, 1000);
    
});
