import pandas as pd
import numpy as np
from pathlib import Path

TEST_DATA_DIR = Path(__file__).resolve().parent / "sample_data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

def generate_clean_dataset() -> Path:
    data = {
        "product_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "product": ["Laptop", "Smartphone", "Headphones", "Monitor", "Keyboard", "Mouse", "Smartwatch", "Tablet", "Printer", "Speaker"],
        "category": ["Electronics", "Electronics", "Audio", "Electronics", "Accessories", "Accessories", "Wearables", "Electronics", "Office", "Audio"],
        "city": ["Mumbai", "Delhi", "Bengaluru", "Mumbai", "Pune", "Delhi", "Mumbai", "Bengaluru", "Pune", "Delhi"],
        "price": [1200.0, 800.0, 150.0, 300.0, 50.0, 25.0, 200.0, 450.0, 250.0, 100.0],
        "quantity": [5, 10, 25, 8, 30, 50, 15, 12, 6, 20],
        "sales": [6000.0, 8000.0, 3750.0, 2400.0, 1500.0, 1250.0, 3000.0, 5400.0, 1500.0, 2000.0],
        "sale_date": ["2025-01-15", "2025-01-16", "2025-01-17", "2025-01-18", "2025-01-19", "2025-01-20", "2025-01-21", "2025-01-22", "2025-01-23", "2025-01-24"],
        "customer": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy"]
    }
    df = pd.DataFrame(data)
    csv_path = TEST_DATA_DIR / "clean_ecommerce.csv"
    excel_path = TEST_DATA_DIR / "clean_ecommerce.xlsx"
    df.to_csv(csv_path, index=False)
    df.to_excel(excel_path, index=False)
    return csv_path

def generate_dirty_dataset() -> Path:
    data = {
        "product_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 101, 102], # 2 duplicate rows
        "product": ["Laptop", "Smartphone", "Headphones", "Monitor", "Keyboard", "Mouse", "Smartwatch", "Tablet", "Printer", "Speaker", "Laptop", "Smartphone"],
        "category": ["Electronics", "Electronics", None, "Electronics", "Accessories", "Accessories", "Wearables", "Electronics", "Office", None, "Electronics", "Electronics"], # Missing missing category
        "city": ["Mumbai", "mumbai", "MUMBAI", "Delhi", "delhi", "Bengaluru", "bengaluru", "Mumbai", "pune", "Pune", "Mumbai", "mumbai"], # Inconsistent casing
        "price": ["$1200", "$800", "$150", "$300", "$50", "$25", "$200", "$450", "$250", "$100", "$1200", "$800"], # Text price
        "age": [25, np.nan, 34, np.nan, 29, 45, np.nan, 52, 31, 28, 25, np.nan], # Missing age
        "sales": [6000.0, 8000.0, 3750.0, 2400.0, 1500.0, 1250.0, 3000.0, 5400.0, 1500.0, 99999.0, 6000.0, 8000.0], # Outlier 99999
        "sale_date": ["2025-01-15", "2025/01/16", "17-01-2025", "2025-01-18", "2025-01-19", "2025-01-20", "invalid_date", "2025-01-22", "2025-01-23", "2025-01-24", "2025-01-15", "2025/01/16"]
    }
    df = pd.DataFrame(data)
    csv_path = TEST_DATA_DIR / "dirty_dataset.csv"
    excel_path = TEST_DATA_DIR / "dirty_dataset.xlsx"
    df.to_csv(csv_path, index=False)
    df.to_excel(excel_path, index=False)
    return csv_path

if __name__ == "__main__":
    c_path = generate_clean_dataset()
    d_path = generate_dirty_dataset()
    print(f"Sample datasets generated successfully at:\n- {c_path}\n- {d_path}")
