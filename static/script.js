// Ketcher Integration - Basic open/close only
document.addEventListener('DOMContentLoaded', function () {
    const ketcherContainer = document.getElementById('ketcher-container');
    const ketcherFrame = document.getElementById('ketcher-frame');
    let ketcherLoaded = false;

    // Open Ketcher button
    document.getElementById('open-ketcher-btn').addEventListener('click', function () {
        ketcherContainer.style.display = 'block';
        if (!ketcherLoaded) {
            ketcherFrame.src = '/static/ketcher/index.html';
            ketcherLoaded = true;
        }
    });

    // Close Ketcher button
    document.getElementById('close-ketcher-btn').addEventListener('click', function () {
        ketcherContainer.style.display = 'none';
    });
});

// LogS Prediction Function
function predictLogS() {
    const smilesList = document.getElementById('smiles-input').value
        .trim()
        .split('\n')
        .filter(s => s.trim() !== '');
    const model = document.getElementById('model-select').value;

    if (smilesList.length === 0) {
        alert('Please enter at least one SMILES string.');
        return;
    }

    const predictButton = document.getElementById('predict-button');
    const originalText = predictButton.textContent;
    predictButton.textContent = 'Processing...';
    predictButton.disabled = true;

    fetch('/predict', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            smiles: smilesList,
            model: model,
        }),
    })
        .then(response => response.json())
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Prediction error: ' + error.message);
        })
        .finally(() => {
            predictButton.textContent = originalText;
            predictButton.disabled = false;
        });
}

// CSV Upload Function
function uploadCSV() {
    const fileInput = document.getElementById('csv-upload');
    const model = document.getElementById('csv-model-select').value;

    if (fileInput.files.length === 0) {
        alert('Please select a file.');
        return;
    }

    const uploadButton = document.getElementById('upload-csv-button');
    const originalText = uploadButton.textContent;
    uploadButton.textContent = 'Processing...';
    uploadButton.disabled = true;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('model', model);

    fetch('/upload_csv', {
        method: 'POST',
        body: formData,
    })
        .then(response => response.json())
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Upload error: ' + error.message);
        })
        .finally(() => {
            uploadButton.textContent = originalText;
            uploadButton.disabled = false;
        });
}

// CSV Download Function
function downloadCSV() {
    const results = document.getElementById('results').dataset.results;
    if (!results) {
        alert('No data to download.');
        return;
    }

    const downloadButton = document.getElementById('download-csv-button');
    const originalText = downloadButton.textContent;
    downloadButton.textContent = 'Preparing...';
    downloadButton.disabled = true;

    fetch('/download_csv', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ results: JSON.parse(results) }),
    })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'results.csv';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Download error: ' + error.message);
        })
        .finally(() => {
            downloadButton.textContent = originalText;
            downloadButton.disabled = false;
        });
}

// PubChem Search Function
function searchPubChem() {
    const query = document.getElementById('pubchem-input').value.trim();
    if (!query) {
        alert('Please enter a name or CID.');
        return;
    }

    const searchButton = document.getElementById('pubchem-search-button');
    const originalText = searchButton.textContent;
    searchButton.textContent = 'Searching...';
    searchButton.disabled = true;

    fetch('/pubchem_search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error); // Throw an error if the server returned an error
            }
            const smilesInput = document.getElementById('smiles-input');
            if (smilesInput.value && !smilesInput.value.endsWith('\n')) {
                smilesInput.value += '\n';
            }
            smilesInput.value += data.smiles; // Add SMILES to the input field
        })
        .catch(error => {
            console.error('Error during PubChem search:', error);
            alert('Search error: ' + error.message);
        })
        .finally(() => {
            searchButton.textContent = originalText;
            searchButton.disabled = false;
        });
}

// Display Results Function
function displayResults(results) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '';
    resultsDiv.dataset.results = JSON.stringify(results);

    results.forEach(result => {
        const resultItem = document.createElement('div');
        resultItem.className = 'result-item';

        if (result.error) {
            resultItem.innerHTML = `
                <strong>SMILES:</strong> ${result.smiles || 'N/A'}<br>
                <span style="color:red;">Error: ${result.error}</span>
            `;
        } else {
            resultItem.innerHTML = `
                <strong>SMILES:</strong> ${result.smiles}<br>
                <img src="${result.image}" alt="Molecule" class="result-image"><br>
                <strong>Prediction:</strong> ${result.prediction?.toFixed(2) || 'N/A'}<br>
                <strong>Solubility:</strong> ${result.solubility || 'N/A'}
            `;
        }
        resultsDiv.appendChild(resultItem);
    });
}

// Theme Switcher
document.getElementById('switch').addEventListener('change', function () {
    document.body.classList.toggle('dark-theme');
    localStorage.setItem('darkTheme', this.checked);
});

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    // Set theme from localStorage
    const darkTheme = localStorage.getItem('darkTheme') === 'true';
    document.getElementById('switch').checked = darkTheme;
    if (darkTheme) document.body.classList.add('dark-theme');

    // Event listeners
    document.getElementById('predict-button').addEventListener('click', predictLogS);
    document.getElementById('upload-csv-button').addEventListener('click', uploadCSV);
    document.getElementById('download-csv-button').addEventListener('click', downloadCSV);
    document.getElementById('pubchem-search-button').addEventListener('click', searchPubChem);
});