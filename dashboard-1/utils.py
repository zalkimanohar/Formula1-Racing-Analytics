import pandas as pd
import os

def load_gold(table):
    base = "../data/gold"
    path = os.path.join(base, table, f"{table}.parquet")
    return pd.read_parquet(path)
