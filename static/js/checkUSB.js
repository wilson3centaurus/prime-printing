// Function to check USB status
async function checkUSBStatus() {
    try {
        const response = await fetch('/files');
        const files = await response.json();
        
        // Filter only supported files
        const supportedFiles = files.filter(file => 
            ['pdf', 'docx', 'jpg', 'jpeg', 'png'].includes(file.type.toLowerCase())
        );
        
        // Redirect to USB page if files are found
        if (supportedFiles.length > 0) {
            window.location.href = 'usb';
        }
    } catch (error) {
        console.error("Error checking USB status:", error);
    }
}

// Check USB status every 1/2 second
setInterval(checkUSBStatus, 500);

// Initial check when page loads
document.addEventListener('DOMContentLoaded', checkUSBStatus);