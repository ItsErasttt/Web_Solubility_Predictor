
document.addEventListener('DOMContentLoaded', function () {
    const ketcherContainer = document.getElementById('ketcher-container');
    const ketcherFrame = document.getElementById('ketcher-frame');
    let ketcherLoaded = false;


    document.getElementById('open-ketcher-btn').addEventListener('click', function () {
        ketcherContainer.style.display = 'block';
        if (!ketcherLoaded) {
            ketcherFrame.src = '/static/ketcher/index.html';
            ketcherLoaded = true;
        }
    });


    document.getElementById('close-ketcher-btn').addEventListener('click', function () {
        ketcherContainer.style.display = 'none';
    });
});


function predictLogS() {
    const smilesList = document.getElementById('smiles-input').value
        .trim()
        .split('\n')
        .filter(s => s.trim() !== '');
    const model = document.getElementById('model-select').value;

    if (smilesList.length === 0) {
        alert('Пожалуйста, введите хотя бы одну SMILES-строку.');
        return;
    }

    const predictButton = document.getElementById('predict-button');
    const originalText = predictButton.textContent;
    predictButton.textContent = 'Обработка...';
    predictButton.disabled = true;

    fetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ smiles: smilesList, model: model }),
    })
    .then(response => response.json())
    .then(data => {
        saveToHistory(data);
        displayResults(data);
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Ошибка предсказания: ' + error.message);
    })
    .finally(() => {
        predictButton.textContent = originalText;
        predictButton.disabled = false;
    });
}


function uploadCSV() {
    const fileInput = document.getElementById('csv-upload');
    const model = document.getElementById('csv-model-select').value;

    if (fileInput.files.length === 0) {
        alert('Пожалуйста, выберите файл.');
        return;
    }

    const uploadButton = document.getElementById('upload-csv-button');
    const originalText = uploadButton.textContent;
    uploadButton.textContent = 'Обработка...';
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
        saveToHistory(data);
        displayResults(data);
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Ошибка загрузки CSV: ' + error.message);
    })
    .finally(() => {
        uploadButton.textContent = originalText;
        uploadButton.disabled = false;
    });
}


function uploadMOL() {
    const fileInput = document.getElementById('mol-upload');
    const model = document.getElementById('mol-model-select').value;

    if (fileInput.files.length === 0) {
        alert('Пожалуйста, выберите файл .mol');
        return;
    }

    const uploadButton = document.getElementById('upload-mol-button');
    const originalText = uploadButton.textContent;
    uploadButton.textContent = 'Обработка...';
    uploadButton.disabled = true;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    fetch('/upload_mol', {
        method: 'POST',
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }


        const smilesInput = document.getElementById('smiles-input');
        if (smilesInput.value && !smilesInput.value.endsWith('\n')) {
            smilesInput.value += '\n';
        }
        smilesInput.value += data.smiles;


        document.getElementById('model-select').value = model;


        predictLogS();
    })
    .catch(error => {
        console.error('Ошибка при загрузке .mol:', error);
        alert('Ошибка загрузки .mol: ' + error.message);
    })
    .finally(() => {
        uploadButton.textContent = originalText;
        uploadButton.disabled = false;
    });
}

function downloadCSV() {
    const resultsDiv = document.getElementById('results');
    const results = JSON.parse(resultsDiv.dataset.results || '[]');

    if (results.length === 0) {
        alert('Нет данных для скачивания.');
        return;
    }

    const downloadButton = document.getElementById('download-csv-button');
    const originalText = downloadButton.textContent;
    downloadButton.textContent = 'Подготовка...';
    downloadButton.disabled = true;

    fetch('/download_csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results: results }),
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
        console.error('Ошибка:', error);
        alert('Ошибка загрузки: ' + error.message);
    })
    .finally(() => {
        downloadButton.textContent = originalText;
        downloadButton.disabled = false;
    });
}


function searchPubChem() {
    const query = document.getElementById('pubchem-input').value.trim();
    if (!query) {
        alert('Пожалуйста, введите запрос.');
        return;
    }

    const searchButton = document.getElementById('pubchem-search-button');
    const originalText = searchButton.textContent;
    searchButton.textContent = 'Поиск...';
    searchButton.disabled = true;

    fetch('/pubchem_search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query }),
    })
    .then(response => {
        if (!response.ok) throw new Error(`HTTP ошибка! Статус: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.error) throw new Error(data.error);

        const smilesInput = document.getElementById('smiles-input');
        if (smilesInput.value && !smilesInput.value.endsWith('\n')) {
            smilesInput.value += '\n';
        }
        smilesInput.value += data.smiles;
    })
    .catch(error => {
        console.error('Ошибка:', error);
        alert('Ошибка поиска: ' + error.message);
    })
    .finally(() => {
        searchButton.textContent = originalText;
        searchButton.disabled = false;
    });
}


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
                <span style="color:red;">Ошибка: ${result.error}</span>
            `;
        } else {
            resultItem.innerHTML = `
                <strong>SMILES:</strong> ${result.smiles}<br>
                <img src="${result.image}" alt="Молекула" class="result-image"><br>
                <strong>Предсказанный logS:</strong> ${result.prediction?.toFixed(2) || 'N/A'}<br>
                <strong>Растворимость:</strong> ${result.solubility || 'N/A'}<br>
                <strong>Класс растворимости:</strong> 
                <span class="${
                    result.solubility_class.includes('Высокая') ? 'prediction-high' :
                    result.solubility_class.includes('Средняя') ? 'prediction-medium' : 'prediction-low'
                }">${result.solubility_class}</span>
            `;
        }

        resultsDiv.appendChild(resultItem);
    });
}


function saveToHistory(data) {
    let history = JSON.parse(localStorage.getItem('predictionHistory') || '[]');
    history = history.concat(data.filter(r => !r.error)); // фильтруем ошибки
    localStorage.setItem('predictionHistory', JSON.stringify(history));
}


document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('predict-button').addEventListener('click', predictLogS);
    document.getElementById('upload-csv-button').addEventListener('click', uploadCSV);
    document.getElementById('upload-mol-button').addEventListener('click', uploadMOL);
    document.getElementById('download-csv-button').addEventListener('click', downloadCSV);
    document.getElementById('pubchem-search-button').addEventListener('click', searchPubChem);
});