from flask import Flask, render_template, request, jsonify, send_file
import joblib
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors, AllChem, Draw
import base64
import io
import os
import requests

app = Flask(__name__)

# Загрузка моделей и scaler
model_logS = joblib.load('models/logS_predictor_model.joblib')
scaler_logS = joblib.load('models/scaler.joblib')

# Загрузка новой модели
model_optimized = joblib.load('models/optimized_rf_model.joblib')
feature_names_new = joblib.load('models/feature_names.joblib')  # Названия признаков для новой модели

# Функция для вычисления молекулярных дескрипторов
def calculate_descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    descriptors = {
        'logP': Descriptors.MolLogP(mol),
        'MW': Descriptors.MolWt(mol),
        'NumHDonors': Lipinski.NumHDonors(mol),
        'NumHAcceptors': Lipinski.NumHAcceptors(mol),
        'TPSA': Descriptors.TPSA(mol),
        'NumRotatableBonds': Lipinski.NumRotatableBonds(mol),
        'NumAromaticRings': rdMolDescriptors.CalcNumAromaticRings(mol),
    }
    return descriptors

# Функция для определения класса растворимости
def classify_solubility(log_s):
    if log_s is None:
        return "Не определено"
    if log_s > 0:
        return "Высокая растворимость"
    elif log_s > -2:
        return "Средняя растворимость"
    else:
        return "Низкая растворимость"

# Функция для предсказания logS (старая модель)
def predict_log_s_old(smiles_list):
    predictions = []
    for smiles in smiles_list:
        descriptors = calculate_descriptors(smiles)
        if descriptors is None:
            predictions.append(None)  # Некорректная SMILES-строка
            continue

        # Создаем DataFrame из дескрипторов
        descriptors_df = pd.DataFrame([descriptors])

        # Добавляем молекулярный отпечаток пальца
        mol = Chem.MolFromSmiles(smiles)
        fingerprint = list(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024))
        fingerprint_df = pd.DataFrame([fingerprint], columns=[f"FP_{i}" for i in range(1024)])

        # Объединяем дескрипторы и отпечаток пальца
        combined_df = pd.concat([descriptors_df, fingerprint_df], axis=1)

        # Оставляем только те колонки, которые ожидаются моделью
        expected_columns = ['logP', 'MW', 'NumHDonors', 'NumHAcceptors', 'TPSA',
                            'NumRotatableBonds', 'NumAromaticRings'] + [f"FP_{i}" for i in range(1024)]
        
        # Добавляем недостающие колонки со значением 0
        for col in expected_columns:
            if col not in combined_df.columns:
                combined_df[col] = 0
        
        # Удаляем лишние колонки
        combined_df = combined_df[expected_columns]

        # Масштабирование данных
        scaled_data = scaler_logS.transform(combined_df)

        # Предсказываем
        prediction = model_logS.predict(scaled_data)[0]
        predictions.append(float(prediction))  # Преобразуем float32 в float
    return predictions

# Функция для предсказания logS (новая модель)
def predict_log_s_new(smiles_list):
    predictions = []
    for smiles in smiles_list:
        descriptors = calculate_descriptors(smiles)
        if descriptors is None:
            predictions.append(None)  # Некорректная SMILES-строка
            continue

        # Создаем DataFrame из дескрипторов
        descriptors_df = pd.DataFrame([descriptors])
        descriptors_df = descriptors_df.reindex(columns=feature_names_new, fill_value=0)

        # Предсказываем
        prediction = model_optimized.predict(descriptors_df)[0]
        predictions.append(float(prediction))  # Преобразуем float32 в float
    return predictions

# Маршрут для главной страницы
@app.route('/')
def index():
    return render_template('index.html')

# Маршрут для предсказания
@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        smiles_list = data.get('smiles', [])
        model_choice = data.get('model', 'old')  # По умолчанию используется старая модель

        if not isinstance(smiles_list, list) or not all(isinstance(smiles, str) for smiles in smiles_list):
            return jsonify({'error': 'Некорректный формат данных'}), 400

        # Выбор модели
        if model_choice == 'new':
            predictions = predict_log_s_new(smiles_list)
        else:
            predictions = predict_log_s_old(smiles_list)

        results = []
        for smiles, prediction in zip(smiles_list, predictions):
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                results.append({
                    'smiles': smiles,
                    'error': 'Некорректная SMILES-строка',
                    'image': None,
                    'prediction': None,
                    'solubility': None,
                    'solubility_class': None
                })
                continue

            # Создаем изображение молекулы
            try:
                img = Draw.MolToImage(mol)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            except Exception as e:
                img_str = None

            # Вычисляем реальную растворимость и класс растворимости
            solubility = f"{10 ** prediction:.4f} моль/л" if prediction is not None else None
            solubility_class = classify_solubility(prediction)

            results.append({
                'smiles': smiles,
                'image': f"data:image/png;base64,{img_str}" if img_str else None,
                'prediction': float(prediction) if prediction is not None else None,
                'solubility': solubility,
                'solubility_class': solubility_class
            })

        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()  # Логируем трассировку ошибки
        return jsonify({'error': str(e)}), 500

# Маршрут для загрузки CSV
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    try:
        df = pd.read_csv(file)
        smiles_list = df['SMILES'].tolist()
        model_choice = request.form.get('model', 'old')

        # Выбор модели
        if model_choice == 'new':
            predictions = predict_log_s_new(smiles_list)
        else:
            predictions = predict_log_s_old(smiles_list)

        results = []
        for smiles, prediction in zip(smiles_list, predictions):
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                results.append({
                    'smiles': smiles,
                    'error': 'Некорректная SMILES-строка',
                    'image': None,
                    'prediction': None,
                    'solubility': None,
                    'solubility_class': None
                })
                continue

            # Создаем изображение молекулы
            try:
                img = Draw.MolToImage(mol)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            except Exception as e:
                img_str = None

            # Вычисляем реальную растворимость и класс растворимости
            solubility = f"{10 ** prediction:.4f} моль/л" if prediction is not None else None
            solubility_class = classify_solubility(prediction)

            results.append({
                'smiles': smiles,
                'image': f"data:image/png;base64,{img_str}" if img_str else None,
                'prediction': float(prediction) if prediction is not None else None,
                'solubility': solubility,
                'solubility_class': solubility_class
            })

        return jsonify(results)
    except Exception as e:
        print(f"Ошибка при обработке CSV: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для скачивания CSV
@app.route('/download_csv', methods=['POST'])
def download_csv():
    try:
        data = request.json
        results = data.get('results', [])
        if not results:
            return jsonify({'error': 'Нет данных для скачивания'}), 400

        # Создаем DataFrame
        df = pd.DataFrame(results)
        df = df[['smiles', 'prediction', 'solubility', 'solubility_class']]  # Оставляем только нужные колонки

        # Сохраняем временный файл
        temp_file = 'results.csv'
        df.to_csv(temp_file, index=False)

        # Отправляем файл пользователю
        return send_file(
            temp_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name='results.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Маршрут для поиска через PubChem
@app.route('/pubchem_search', methods=['POST'])
def pubchem_search():
    try:
        data = request.json
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Запрос пустой'}), 400

        # Проверяем, является ли запрос CID (число)
        if query.isdigit():
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{query}/property/CanonicalSMILES/JSON"
        else:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/CanonicalSMILES/JSON"

        # Отправляем запрос к API PubChem
        response = requests.get(url)

        # Проверяем статус ответа
        if response.status_code != 200:
            return jsonify({'error': 'Молекула не найдена в PubChem'}), 404

        # Парсим JSON-ответ
        data = response.json()
        if 'PropertyTable' not in data or 'Properties' not in data['PropertyTable']:
            return jsonify({'error': 'Ошибка при получении данных из PubChem'}), 500

        # Извлекаем SMILES
        smiles = data['PropertyTable']['Properties'][0].get('CanonicalSMILES')
        if not smiles:
            return jsonify({'error': 'SMILES не найден для данного запроса'}), 404

        return jsonify({'smiles': smiles})
    except Exception as e:
        print(f"Ошибка при поиске в PubChem: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)