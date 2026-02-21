import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import os
import sys

sys.path.append(os.path.dirname(__file__))
from app.models.database import SessionLocal
from app.models.models import CreditApplication

MODEL_PATH = os.path.join(os.path.dirname(__file__), "credit_model.pkl")
DATASET_PATH = os.path.join(os.path.dirname(__file__), "final_dataset.csv")

def train_credit_model():
    X_data = []
    y_data = []

    if os.path.exists(DATASET_PATH):
        print(f"Загрузка реального датасета: {DATASET_PATH}")
        try:
            df = pd.read_csv(DATASET_PATH)
            
            required_cols = ['current_ratio', 'debt_to_equity', 'net_profit_margin', 'company_age', 'target']
            if all(col in df.columns for col in required_cols):
                df = df.dropna(subset=required_cols)
                
                features = df[['current_ratio', 'debt_to_equity', 'net_profit_margin', 'company_age']].values
                targets = df['target'].values
                
                for i in range(len(features)):
                    X_data.append(features[i])
                    y_data.append(targets[i])
                    
                print(f"Загружено строк из файла: {len(X_data)}")
            else:
                print("Ошибка: В CSV не хватает нужных колонок.")
        except Exception as e:
            print(f"Ошибка чтения CSV: {e}")
    else:
        print(f"Файл {DATASET_PATH} не найден. Пропускаем загрузку файла.")

    # --- 2. Загрузка данных из Базы Данных (История заявок) ---
    try:
        db = SessionLocal()
        apps = db.query(CreditApplication).all()
        
        db_count = 0
        for app in apps:
            fin = app.financial_data
            if not fin: continue
            
            # Собираем признаки
            x_row = [
                fin.get("current_ratio", 1.0),
                fin.get("debt_to_equity", 1.0),
                fin.get("net_profit_margin", 0.05),
                fin.get("company_age", 3)
            ]
            
            # Если рейтинг не был проставлен, считаем его на лету по правилам
            # (или используем app.rating если он есть и корректен)
            if app.rating is None or app.rating == 0:
                calc_rating = 100
                if x_row[0] < 1.5: calc_rating -= 40
                if x_row[1] > 2.0: calc_rating -= 20
                
                target = 1 if calc_rating < 50 else 0
            else:
                target = 1 if app.rating < 50 else 0

            X_data.append(x_row)
            y_data.append(target)
            db_count += 1
            
        print(f"Загружено строк из Базы Данных: {db_count}")
        db.close()
    except Exception as e:
        print(f"Не удалось подключиться к БД (возможно, она пуста): {e}")

    # --- 3. Синтетика (только если данных критически мало) ---
    if len(X_data) < 10:
        print("Данных мало, добавляем синтетику...")
        synthetic_X = np.array([
            [2.0, 1.0, 0.15, 10], [1.8, 0.5, 0.10, 5], [2.5, 0.8, 0.20, 8],
            [0.8, 3.0, -0.05, 1], [1.1, 2.5, 0.01, 2], [0.5, 4.0, -0.1, 1]
        ])
        synthetic_y = np.array([0, 0, 0, 1, 1, 1])
        
        if len(X_data) > 0:
            X_data = np.concatenate([np.array(X_data), synthetic_X])
            y_data = np.concatenate([np.array(y_data), synthetic_y])
        else:
            X_data = synthetic_X
            y_data = synthetic_y
    else:
        # Конвертируем в numpy array для скорости
        X_data = np.array(X_data)
        y_data = np.array(y_data)

    # --- 4. Обучение ---
    if len(X_data) == 0:
        print("ОШИБКА: Нет данных для обучения!")
        return

    print(f"Начинаем обучение на {len(X_data)} примерах...")
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_data, y_data)
    
    # Сохраняем модель
    joblib.dump(model, MODEL_PATH)
    print(f"Модель сохранена в {MODEL_PATH}")
    
    # Проверка важности признаков (для информации)
    importances = model.feature_importances_
    print("Важность признаков:")
    print(f"  Ликвидность: {importances[0]:.2f}")
    print(f"  Долг:        {importances[1]:.2f}")
    print(f"  Рентабельн.: {importances[2]:.2f}")
    print(f"  Возраст:     {importances[3]:.2f}")

if __name__ == "__main__":
    train_credit_model()