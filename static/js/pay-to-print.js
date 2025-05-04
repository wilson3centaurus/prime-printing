const url = "{{ file_url }}";
const container = document.getElementById('pdf-container');

pdfjsLib.getDocument(url).promise.then(pdf => {
    for (let i = 1; i <= pdf.numPages; i++) {
        pdf.getPage(i).then(page => {
            const viewport = page.getViewport({ scale: 1.5 });
            const canvas = document.createElement('canvas');
            const div = document.createElement('div');
            div.className = 'page-container';
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            div.appendChild(canvas);
            container.appendChild(div);
            page.render({
                canvasContext: canvas.getContext('2d'),
                viewport: viewport
            });
        });
    }
}).catch(error => {
    console.error("PDF loading error:", error);
    container.innerHTML = `
        <div class="error-container text-center">
            <div class="error-icon">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <h2 class="text-xl font-bold mb-4">Could not preview "{{ filename }}"</h2>
            <div class="mt-6">
                <button class="btn" onclick="window.history.back()">
                    <i class="fas fa-arrow-left"></i> Go Back
                </button>
                <button class="btn" onclick="window.location.reload()">
                    <i class="fas fa-sync-alt"></i> Try Again
                </button>
            </div>
        </div>
    `;
});

// Modal functionality
const printBtn = document.getElementById('print-btn');
const printModal = document.getElementById('print-modal');
const printForm = document.getElementById('printForm');
const form = document.getElementById('printForm');
const statusBox = document.getElementById('statusBox');
const statusText = document.getElementById('statusText');
const selectedPagesSpan = document.getElementById('selectedPages');
const totalPages = 5; // This should be set to the actual number of pages
const costPerPage = 0.10;

printBtn.addEventListener('click', () => {
    printModal.classList.remove('hidden');
    printModal.classList.add('flex');
});

form.addEventListener('submit', function (e) {
    e.preventDefault();
    const copies = parseInt(form.copies.value) || 1;
    const pagesInput = form.pages.value.trim().toLowerCase();
    let pagesCount = totalPages;
    let pagesDescription = "All";

    printForm.style.display = 'none';

    // Custom page selection parsing
    if (pagesInput && pagesInput !== "all") {
        if (pagesInput === "odd") {
            pagesCount = Math.ceil(totalPages / 2);
            pagesDescription = "Odd pages";
        } else if (pagesInput === "even") {
            pagesCount = Math.floor(totalPages / 2);
            pagesDescription = "Even pages";
        } else {
            const pages = pagesInput.split(",").map(p => parseInt(p.trim())).filter(p => p > 0 && p <= totalPages);
            pagesCount = [...new Set(pages)].length;
            pagesDescription = pagesInput;
        }
    }

    const totalCost = (pagesCount * copies * costPerPage).toFixed(2);
    document.getElementById("totalCost").textContent = totalCost;
    selectedPagesSpan.textContent = pagesDescription;

    // Show processing status
    statusBox.classList.remove('hidden');
    statusText.textContent = "Processing payment...";

    // Simulate payment (replace this with real API call)
    setTimeout(() => {
        statusText.textContent = "Payment successful ✅ Printing started...";
        setTimeout(() => {
            // Simulate print
            window.print();
            printModal.classList.add('hidden');
            statusBox.classList.add('hidden');
        }, 1500);
    }, 2000);
});

// Update page count and cost when inputs change
form.pages.addEventListener('input', updateCost);
form.copies.addEventListener('input', updateCost);

function updateCost() {
    const copies = parseInt(form.copies.value) || 1;
    const pagesInput = form.pages.value.trim().toLowerCase();
    let pagesCount = totalPages;

    if (pagesInput && pagesInput !== "all") {
        if (pagesInput === "odd") {
            pagesCount = Math.ceil(totalPages / 2);
        } else if (pagesInput === "even") {
            pagesCount = Math.floor(totalPages / 2);
        } else {
            const pages = pagesInput.split(",").map(p => parseInt(p.trim())).filter(p => p > 0 && p <= totalPages);
            pagesCount = [...new Set(pages)].length;
        }
    }

    const totalCost = (pagesCount * copies * costPerPage).toFixed(2);
    document.getElementById("totalCost").textContent = totalCost;
}
