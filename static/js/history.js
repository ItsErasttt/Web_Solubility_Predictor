document.addEventListener('DOMContentLoaded', function () {
    const historyContainer = document.getElementById('history-results');
    const emptyMessage = document.getElementById('empty-history');

    
    function loadHistory() {
        return JSON.parse(localStorage.getItem('predictionHistory') || '[]');
    }

    function saveHistory(history) {
        localStorage.setItem('predictionHistory', JSON.stringify(history));
    }

    function renderHistory() {
        const history = loadHistory();

        if (history.length === 0) {
            emptyMessage.style.display = 'block';
            historyContainer.innerHTML = '';
            return;
        } else {
            emptyMessage.style.display = 'none';
        }

        historyContainer.innerHTML = ''; 

        history.forEach((item, index) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'history-item card';

            itemDiv.innerHTML = `
                <div class="history-header">
                    <strong>SMILES:</strong> ${item.smiles}<br>
                    <strong>logS:</strong> ${item.prediction?.toFixed(2) || 'N/A'}<br>
                    <strong>Растворимость:</strong> ${item.solubility || 'N/A'}<br>
                    <strong>Класс растворимости:</strong>
                    <span class="${getSolubilityClass(item.solubility_class)}">${item.solubility_class}</span>
                </div>
                <img src="${item.image}" alt="Молекула" class="result-image"><br>
                <div class="history-actions">
                    <button onclick="repeatPrediction('${item.smiles}')" class="btn-primary">🔄 Повторить</button>
                    <button onclick="downloadSingle(${index})" class="btn-success">💾 Скачать</button>
                </div>
            `;

            historyContainer.appendChild(itemDiv);
        });
    }

    function getSolubilityClass(solubilityClass) {
        if (!solubilityClass) return '';
        if (solubilityClass.includes('Высокая')) return 'prediction-high';
        if (solubilityClass.includes('Средняя')) return 'prediction-medium';
        if (solubilityClass.includes('Низкая')) return 'prediction-low';
        return '';
    }




    document.getElementById('clear-history').addEventListener('click', () => {
        if (confirm('Вы уверены, что хотите очистить историю?')) {
            localStorage.removeItem('predictionHistory');
            renderHistory();
        }
    });


    document.getElementById('download-all').addEventListener('click', () => {
        const history = loadHistory();
        if (history.length === 0) {
            alert('История пуста. Нечего скачивать.');
            return;
        }

        const csvRows = [
            ['SMILES', 'logS', 'Растворимость', 'Класс растворимости']
        ];

        history.forEach(item => {
            csvRows.push([
                item.smiles,
                item.prediction?.toFixed(2),
                item.solubility || '',
                item.solubility_class || ''
            ]);
        });

        const csvContent = csvRows.map(row => row.join(",")).join("\n");
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.setAttribute("href", url);
        a.setAttribute("download", "history.csv");
        a.click();
    });



    window.repeatPrediction = function(smiles) {

        window.location.href = '/';
        setTimeout(() => {
            const smilesInput = document.getElementById('smiles-input');
            const predictButton = document.getElementById('predict-button');

            if (smilesInput && predictButton) {
                if (smilesInput.value && !smilesInput.value.endsWith('\n')) {
                    smilesInput.value += '\n';
                }
                smilesInput.value += smiles;
                predictButton.scrollIntoView({ behavior: 'smooth' });
            }
        }, 500);
    };

    window.downloadSingle = function(index) {
        const history = loadHistory();
        const item = history[index];

        if (!item) {
            alert('Не удалось найти запись для скачивания.');
            return;
        }

        const csvContent = [
            ['SMILES', 'logS', 'Растворимость', 'Класс растворимости'],
            [item.smiles, item.prediction?.toFixed(2), item.solubility || '', item.solubility_class || '']
        ].map(row => row.join(",")).join("\n");

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        a.download = `history_item_${index}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    };

    renderHistory();
});