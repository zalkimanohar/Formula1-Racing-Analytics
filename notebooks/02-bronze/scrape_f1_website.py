import os
import io
import requests
from bs4 import BeautifulSoup
import pandas as pd

TARGET_URL = "https://www.formula1.com/en/results/2026/races"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def scrape_f1_races_page():
    print(f"🌐 Requesting race results from: {TARGET_URL}")
    response = requests.get(TARGET_URL, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"❌ Failed to access page. Status code: {response.status_code}")
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    tables = soup.find_all('table')
    
    if not tables:
        print("⚠️ No static HTML table found.")
        return None
        
    df = pd.read_html(io.StringIO(str(tables[0])))[0]
    workspace = os.getenv("WORKSPACE", "/Users/manoharazalki/F1-Analytics")
    landing_base = os.path.join(workspace, "data/landing")
    
    # Write scraped races.csv across all existing landing partitions
    partition_folders = [f for f in os.listdir(landing_base) if f.startswith("2026-")]
    
    for folder in partition_folders:
        path = os.path.join(landing_base, folder, "races.csv")
        df.to_csv(path, index=False)
        
    print(f"✅ Successfully updated races.csv across {len(partition_folders)} landing folders!")
    return df

if __name__ == "__main__":
    scrape_f1_races_page()
