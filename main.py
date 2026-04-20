import sys
from src.data_cleaning import clean_data
from src.import_to_db import import_data

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    clean_data()
    import_data()