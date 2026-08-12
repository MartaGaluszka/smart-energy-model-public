import os
import sys
import joblib
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# Dodanie ścieżki do projektu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.features.pv_features_hourly_extended import load_hourly_training_frame_extended, TARGET_COLUMN

# 1. Automatyczne daty: od 1 czerwca do dziś (włącznie z częściowym dniem bieżącym)
start_date = '2026-06-01'
end_date = datetime.now().strftime('%Y-%m-%d')
print(f"Pobieram dane dla zakresu: {start_date} do {end_date}")

# 2. Wczytaj model (Pipeline)
loaded_data = joblib.load('models/pv_hourly_model.joblib')
model = loaded_data['pipeline']
features = loaded_data['feature_columns']

# 3. Wczytaj dane produkcyjne
df_prod = load_hourly_training_frame_extended(start_date=start_date, end_date=end_date)

# 4. Oblicz predykcję
df_prod['pred'] = model.predict(df_prod[features])

# 5. Przygotuj daty dla osi X
df_prod['timestamp'] = pd.to_datetime(df_prod['day']) + pd.to_timedelta(df_prod['hour'], unit='h')

# 6. Wykres (cały zakres)
plt.figure(figsize=(15, 6))
plt.plot(df_prod['timestamp'], df_prod['pred'], label='Predykcja (Model)', alpha=0.8)
plt.plot(df_prod['timestamp'], df_prod[TARGET_COLUMN], label='Rzeczywistość (Produkcja)', alpha=0.6)

plt.title(f'Weryfikacja modelu: {start_date} do {end_date}', fontsize=14)
plt.xlabel('Data i czas')
plt.ylabel('PV kWh/h')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('reports/figures/production_validation.png', dpi=150, bbox_inches='tight')
plt.close()
print('✓ reports/figures/production_validation.png')