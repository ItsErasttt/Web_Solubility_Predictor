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

# Загрузка моделей и скалеров
model_logS = joblib.load('models/logS_predictor_model.joblib')
scaler_logS = joblib.load('models/scaler.joblib')

model_optimized = joblib.load('models/optimized_rf_model.joblib')
feature_names_new = joblib.load('models/feature_names.joblib')  # Признаки новой модели

# === Утилиты ===

def calculate_descriptors(smiles):
    """Вычисление молекулярных дескрипторов"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return {
        'logP': Descriptors.MolLogP(mol),
        'MW': Descriptors.MolWt(mol),
        'NumHDonors': Lipinski.NumHDonors(mol),
        'NumHAcceptors': Lipinski.NumHAcceptors(mol),
        'TPSA': Descriptors.TPSA(mol),
        'NumRotatableBonds': Lipinski.NumRotatableBonds(mol),
        'NumAromaticRings': rdMolDescriptors.CalcNumAromaticRings(mol),
    }

def classify_solubility(log_s):
    """Классификация растворимости по значению logS"""
    if log_s is None:
        return "Не определено"
    if log_s > 0:
        return "Высокая растворимость"
    elif log_s > -2:
        return "Средняя растворимость"
    else:
        return "Низкая растворимость"

def smiles_from_mol(mol_content):
    """Преобразует MOL в SMILES"""
    mol = Chem.MolFromMolBlock(mol_content)
    if mol:
        return Chem.MolToSmiles(mol)
    return None

# === Предсказание LogS ===

def predict_log_s_old(smiles_list):
    predictions = []
    for smiles in smiles_list:
        descriptors = calculate_descriptors(smiles)
        if descriptors is None:
            predictions.append(None)
            continue
        descriptors_df = pd.DataFrame([descriptors])
        mol = Chem.MolFromSmiles(smiles)
        fingerprint = list(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024))
        fingerprint_df = pd.DataFrame([fingerprint], columns=[f"FP_{i}" for i in range(1024)])
        combined_df = pd.concat([descriptors_df, fingerprint_df], axis=1)
        expected_columns = ['logP', 'MW', 'NumHDonors', 'NumHAcceptors', 'TPSA',
                            'NumRotatableBonds', 'NumAromaticRings'] + [f"FP_{i}" for i in range(1024)]
        for col in expected_columns:
            if col not in combined_df.columns:
                combined_df[col] = 0
        combined_df = combined_df[expected_columns]
        scaled_data = scaler_logS.transform(combined_df)
        prediction = model_logS.predict(scaled_data)[0]
        predictions.append(float(prediction))
    return predictions

def predict_log_s_new(smiles_list):
    predictions = []
    for smiles in smiles_list:
        descriptors = calculate_descriptors(smiles)
        if descriptors is None:
            predictions.append(None)
            continue
        descriptors_df = pd.DataFrame([descriptors]).reindex(columns=feature_names_new, fill_value=0)
        prediction = model_optimized.predict(descriptors_df)[0]
        predictions.append(float(prediction))
    return predictions

# === Маршруты ===

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        smiles_list = data.get('smiles', [])
        model_choice = data.get('model', 'old')
        if not isinstance(smiles_list, list) or not all(isinstance(smiles, str) for smiles in smiles_list):
            return jsonify({'error': 'Некорректный формат данных'}), 400

        predict_func = predict_log_s_new if model_choice == 'new' else predict_log_s_old
        results = []

        for smiles in smiles_list:
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

            prediction = predict_func([smiles])[0]
            solubility = f"{10 ** prediction:.4f} моль/л" if prediction is not None else None
            solubility_class = classify_solubility(prediction)

            try:
                img = Draw.MolToImage(mol)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            except Exception:
                img_str = None

            results.append({
                'smiles': smiles,
                'image': f"data:image/png;base64,{img_str}" if img_str else None,
                'prediction': prediction,
                'solubility': solubility,
                'solubility_class': solubility_class
            })

        return jsonify(results)

    except Exception as e:
        app.logger.error(f"Ошибка при предсказании: {e}")
        return jsonify({'error': str(e)}), 500

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
        predict_func = predict_log_s_new if model_choice == 'new' else predict_log_s_old

        results = []
        for smiles in smiles_list:
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

            prediction = predict_func([smiles])[0]
            solubility = f"{10 ** prediction:.4f} моль/л" if prediction is not None else None
            solubility_class = classify_solubility(prediction)

            try:
                img = Draw.MolToImage(mol)
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            except Exception:
                img_str = None

            results.append({
                'smiles': smiles,
                'image': f"data:image/png;base64,{img_str}" if img_str else None,
                'prediction': prediction,
                'solubility': solubility,
                'solubility_class': solubility_class
            })

        return jsonify(results)

    except Exception as e:
        app.logger.error(f"Ошибка при загрузке CSV: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload_mol', methods=['POST'])
def upload_mol():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    try:
        mol_content = file.read().decode('utf-8')
        smiles = smiles_from_mol(mol_content)
        if not smiles:
            return jsonify({'error': 'Не удалось извлечь SMILES из файла .mol'}), 400

        mol = Chem.MolFromSmiles(smiles)
        try:
            img = Draw.MolToImage(mol)
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception:
            img_str = None

        return jsonify({
            'smiles': smiles,
            'image': f"data:image/png;base64,{img_str}" if img_str else None
        })

    except Exception as e:
        app.logger.error(f"Ошибка при обработке .mol: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_csv', methods=['POST'])
def download_csv():
    try:
        data = request.json
        results = data.get('results', [])
        if not results:
            return jsonify({'error': 'Нет данных для скачивания'}), 400

        df = pd.DataFrame(results)
        df = df[['smiles', 'prediction', 'solubility', 'solubility_class']]
        temp_file = 'results.csv'
        df.to_csv(temp_file, index=False)

        return send_file(
            temp_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name='results.csv'
        )

    except Exception as e:
        app.logger.error(f"Ошибка при скачивании CSV: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/pubchem_search', methods=['POST'])
def pubchem_search():
    try:
        data = request.json
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Запрос пустой'}), 400

        if query.isdigit():
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{query}/property/CanonicalSMILES/JSON" 
        else:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/CanonicalSMILES/JSON" 

        response = requests.get(url)
        if response.status_code != 200:
            return jsonify({'error': 'Молекула не найдена в PubChem'}), 404

        data = response.json()
        if 'PropertyTable' not in data or 'Properties' not in data['PropertyTable']:
            return jsonify({'error': 'Ошибка при получении данных из PubChem'}), 500

        smiles = data['PropertyTable']['Properties'][0].get('CanonicalSMILES')
        if not smiles:
            return jsonify({'error': 'SMILES не найден для данного запроса'}), 404

        return jsonify({'smiles': smiles})

    except Exception as e:
        app.logger.error(f"Ошибка при поиске в PubChem: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/history', methods=['GET'])
def get_history():
    """Возвращает всю историю из localStorage (через API)"""
    # На стороне клиента это хранится в localStorage, так что этот маршрут просто открывает страницу
    return render_template('history.html')

@app.route('/save_to_history', methods=['POST'])
def save_to_history():
    """Сохраняет результаты в историю (на клиентской стороне)"""
    data = request.json
    return jsonify({"status": "ok", "message": "Результаты сохранены в localStorage"})



if __name__ == '__main__':
    app.run(debug=True)