import pandas as pd
import numpy as np

INPUT_FILE = 'dataset_.csv'
OUTPUT_FILE = 'final_dataset.csv'

def prepare_clean_data():
    print("Обработка данных с учетом пропусков...")
    
    # 1. Читаем файл вручную, чтобы обойти проблему ARFF
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    columns = []
    data_rows = []
    data_section = False
    
    # Ищем индексы колонок
    idx_rating = -1
    idx_curr = -1
    idx_debt = -1
    idx_profit = -1

    for line in lines:
        line = line.strip()
        
        if line.lower().startswith('@attribute'):
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[1].replace('{', '').replace('}', '').lower()
                columns.append(col_name)
                
                # Запоминаем индексы
                if 'rating' == col_name and idx_rating == -1: idx_rating = len(columns)-1
                if 'currentratio' in col_name: idx_curr = len(columns)-1
                if 'debtequityratio' in col_name: idx_debt = len(columns)-1
                if 'netprofitmargin' in col_name: idx_profit = len(columns)-1

        if line.lower().startswith('@data'):
            data_section = True
            continue
            
        if data_section and line and not line.startswith('%'):
            data_rows.append(line.split(','))

    print(f"Индексы: Rating={idx_rating}, Current={idx_curr}, Debt={idx_debt}, Profit={idx_profit}")
    
    # 2. Списки для сбора данных (чтобы потом заполнить пропуски)
    all_curr = []
    all_debt = []
    all_profit = []
    
    raw_data = []

    # 3. Парсим строки
    for row in data_rows:
        try:
            # Функция безопасного получения числа
            def get_num(idx):
                if idx == -1 or idx >= len(row): return np.nan
                val = row[idx].strip()
                if val in ['?', '', 'nan', 'NaN']: return np.nan
                try: return float(val)
                except: return np.nan

            r = get_num(idx_curr)
            d = get_num(idx_debt)
            p = get_num(idx_profit)
            
            # Рейтинг
            rating_val = row[idx_rating].strip().upper() if idx_rating != -1 and idx_rating < len(row) else ""
            
            # Собираем числа для статистики (только валидные)
            if not np.isnan(r): all_curr.append(r)
            if not np.isnan(d): all_debt.append(d)
            if not np.isnan(p): all_profit.append(p)
            
            raw_data.append({
                'rating': rating_val,
                'current_ratio': r,
                'debt_to_equity': d,
                'net_profit_margin': p
            })
        except Exception as e:
            pass

    # Считаем средние (для заполнения пропусков)
    mean_curr = np.mean(all_curr) if all_curr else 1.0
    mean_debt = np.mean(all_debt) if all_debt else 1.0
    mean_profit = np.mean(all_profit) if all_profit else 0.05
    
    print(f"Средние значения: Liq={mean_curr:.2f}, Debt={mean_debt:.2f}, Prof={mean_profit:.2f}")

    # 4. Финальная сборка
    final_data = []
    
    # Список ПЛОХИХ рейтингов (BB и ниже - это риск)
    bad_ratings = ['BB', 'B', 'CCC', 'CC', 'C', 'D', 'SD', 'R']
    
    for item in raw_data:
        # Заполняем пропуски средними
        cr = item['current_ratio'] if not np.isnan(item['current_ratio']) else mean_curr
        de = item['debt_to_equity'] if not np.isnan(item['debt_to_equity']) else mean_debt
        pm = item['net_profit_margin'] if not np.isnan(item['net_profit_margin']) else mean_profit
        
        # Определяем Target
        # Если рейтинг в списке плохих -> 1
        # Иначе -> 0
        target = 1 if item['rating'] in bad_ratings else 0
        
        final_data.append({
            'current_ratio': cr,
            'debt_to_equity': de,
            'net_profit_margin': pm,
            'company_age': 5.0, # Фикс
            'target': target
        })
        
    df = pd.DataFrame(final_data)
    df.to_csv(OUTPUT_FILE, index=False)
    
    print(f"\nФайл создан: {OUTPUT_FILE}")
    print(f"Всего строк: {len(df)}")
    print("Статистика Target (0 - хороший, 1 - плохой):")
    print(df['target'].value_counts())
    
    if (df['target'] == 1).sum() > 0:
        print("\nУСПЕХ! Найдены рискованные компании. Датасет готов к обучению.")
    else:
        print("\nВнимание: Рискованных компаний по-прежнему 0.")

if __name__ == "__main__":
    prepare_clean_data()