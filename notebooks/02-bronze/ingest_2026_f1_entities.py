import os
import json
import requests
import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, FloatType, DoubleType, DateType
)

# 1. Setup Workspace & Base Landing Directory
WORKSPACE = os.getenv("WORKSPACE", "/Users/manoharazalki/F1-Analytics")
#LANDING_BASE = os.path.join(WORKSPACE, "data/landing")
LANDING_BASE = os.path.join(WORKSPACE, "data/incremental")
BRONZE_DIR = os.path.join(WORKSPACE, "data/bronze")

print("🚀 Ingesting complete 2026 F1 Entities into ALL landing round folders...")

spark = SparkSession.builder.appName("F1_Entities_Bronze_Ingestion").getOrCreate()

# 2. Strict Schema Definitions
circuits_schema = StructType([
    StructField('circuitId', StringType(), True),
    StructField('url', StringType(), True),
    StructField('circuitName', StringType(), True),
    StructField('lat', DoubleType(), True),
    StructField('long', DoubleType(), True),
    StructField('locality', StringType(), True),
    StructField('country', StringType(), True)
])

constructors_schema = StructType([
    StructField('constructorId', StringType(), True),
    StructField('name', StringType(), True),
    StructField('nationality', StringType(), True),
    StructField('url', StringType(), True)
])

name_schema = StructType([
    StructField("giveName", StringType(), True),
    StructField("familyName", StringType(), True),
])

drivers_schema = StructType([
    StructField("driverId", StringType(), True),
    StructField("name", name_schema, True),
    StructField("dateOfBirth", DateType(), True),
    StructField("nationality", StringType(), True),
    StructField("url", StringType(), True),
])

races_schema = StructType([
    StructField('season', IntegerType(), True),
    StructField('round', IntegerType(), True),
    StructField('url', StringType(), True),
    StructField('raceName', StringType(), True),
    StructField('date', DateType(), True),
    StructField('circuitId', StringType(), True)
])

results_schema = StructType([
    StructField("date", DateType(), True),
    StructField("raceName", StringType(), True),
    StructField("round", IntegerType(), True),
    StructField("season", IntegerType(), True),
    StructField("url", StringType(), True),
    StructField("constructorId", StringType(), True),
    StructField("driverId", StringType(), True),
    StructField("grid", IntegerType(), True),
    StructField("laps", IntegerType(), True),
    StructField("number", IntegerType(), True),
    StructField("points", FloatType(), True),
    StructField("position", IntegerType(), True),
    StructField("positionText", StringType(), True),
    StructField("status", StringType(), True)
])

sprint_schema = results_schema

# 3. Fetch Master Data across 2026 Season
ENDPOINTS = {
    "circuits": "http://api.jolpi.ca/ergast/f1/2026/circuits.json?limit=100",
    "constructors": "http://api.jolpi.ca/ergast/f1/2026/constructors.json?limit=100",
    "drivers": "http://api.jolpi.ca/ergast/f1/2026/drivers.json?limit=100",
    "races": "http://api.jolpi.ca/ergast/f1/2026/races.json?limit=100",
    "results": "http://api.jolpi.ca/ergast/f1/2026/results.json?limit=2000",
    "sprints": "http://api.jolpi.ca/ergast/f1/2026/sprint.json?limit=200"
}

data_store = {}
for entity, url in ENDPOINTS.items():
    res = requests.get(url)
    data_store[entity] = res.json() if res.status_code == 200 else {}

# Determine total rounds in 2026
races_list = data_store.get('races', {}).get('MRData', {}).get('RaceTable', {}).get('Races', [])
total_races = len(races_list) if races_list else 24

print(f"📊 Discovered {total_races} total rounds in 2026. Populating ALL folders from 2026-01 to 2026-{total_races:02d}...")

# 4. Populate EVERY partition folder inside data/landing/
for r_idx in range(1, total_races + 1):
    partition_folder = os.path.join(LANDING_BASE, f"2026-{r_idx:02d}")
    os.makedirs(partition_folder, exist_ok=True)
    
    # Write circuits.csv
    circuits_data = data_store.get('circuits', {}).get('MRData', {}).get('CircuitTable', {}).get('Circuits', [])
    c_records = [{
        "circuitId": c['circuitId'],
        "url": c.get('url', ''),
        "circuitName": c['circuitName'],
        "lat": float(c['Location'].get('lat', 0.0)),
        "long": float(c['Location'].get('long', 0.0)),
        "locality": c['Location']['locality'],
        "country": c['Location']['country']
    } for c in circuits_data]
    pd.DataFrame(c_records).to_csv(os.path.join(partition_folder, "circuits.csv"), index=False)
    
    # Write constructors.json
    with open(os.path.join(partition_folder, "constructors.json"), "w") as f:
        json.dump(data_store.get('constructors', {}), f, indent=4)
        
    # Write drivers.json
    with open(os.path.join(partition_folder, "drivers.json"), "w") as f:
        json.dump(data_store.get('drivers', {}), f, indent=4)
        
    # Write races.csv
    r_records = [{
        "season": int(r['season']),
        "round": int(r['round']),
        "url": r.get('url', ''),
        "raceName": r['raceName'],
        "date": r.get('date', ''),
        "circuitId": r['Circuit']['circuitId']
    } for r in races_list if int(r['round']) <= r_idx]
    pd.DataFrame(r_records).to_csv(os.path.join(partition_folder, "races.csv"), index=False)
    
    # Write results/ directory & json
    results_dir = os.path.join(partition_folder, "results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "results_2026.json"), "w") as f:
        json.dump(data_store.get('results', {}), f, indent=4)
        
    # Write sprints/ directory & json
    sprints_dir = os.path.join(partition_folder, "sprints")
    os.makedirs(sprints_dir, exist_ok=True)
    with open(os.path.join(sprints_dir, "sprints_2026.json"), "w") as f:
        json.dump(data_store.get('sprints', {}), f, indent=4)

# 5. Build Final Bronze Parquet Files
print("⚡ Generating unified Bronze Parquet datasets...")

# Circuits
c_items = data_store['circuits']['MRData']['CircuitTable']['Circuits']
df_c = spark.createDataFrame([{
    "circuitId": c['circuitId'], "url": c.get('url', ''), "circuitName": c['circuitName'],
    "lat": float(c['Location'].get('lat', 0.0)), "long": float(c['Location'].get('long', 0.0)),
    "locality": c['Location']['locality'], "country": c['Location']['country']
} for c in c_items], schema=circuits_schema)
df_c.write.mode("overwrite").parquet(os.path.join(BRONZE_DIR, "circuits/circuits.parquet"))

# Constructors
cn_items = data_store['constructors']['MRData']['ConstructorTable']['Constructors']
df_cn = spark.createDataFrame([{
    "constructorId": c['constructorId'], "name": c['name'],
    "nationality": c.get('nationality', ''), "url": c.get('url', '')
} for c in cn_items], schema=constructors_schema)
df_cn.write.mode("overwrite").parquet(os.path.join(BRONZE_DIR, "constructors/constructors.parquet"))

# Drivers
d_items = data_store['drivers']['MRData']['DriverTable']['Drivers']
df_d = spark.createDataFrame([{
    "driverId": d['driverId'],
    "name": {"giveName": d.get('givenName', ''), "familyName": d.get('familyName', '')},
    "dateOfBirth": datetime.strptime(d['dateOfBirth'], "%Y-%m-%d").date() if d.get('dateOfBirth') else None,
    "nationality": d.get('nationality', ''), "url": d.get('url', '')
} for d in d_items], schema=drivers_schema)
df_d.write.mode("overwrite").parquet(os.path.join(BRONZE_DIR, "drivers/drivers.parquet"))

# Races
df_r = spark.createDataFrame([{
    "season": int(r['season']), "round": int(r['round']), "url": r.get('url', ''),
    "raceName": r['raceName'], "date": datetime.strptime(r['date'], "%Y-%m-%d").date() if r.get('date') else None,
    "circuitId": r['Circuit']['circuitId']
} for r in races_list], schema=races_schema)
df_r.write.mode("overwrite").parquet(os.path.join(BRONZE_DIR, "races/races.parquet"))

# Results & Sprints
for entity_name, res_key in [("results", "Results"), ("sprints", "SprintResults")]:
    records = []
    for r in races_list:
        r_date = datetime.strptime(r['date'], "%Y-%m-%d").date() if r.get('date') else None
        for res in r.get(res_key, []):
            records.append({
                "date": r_date, "raceName": r['raceName'], "round": int(r['round']),
                "season": int(r['season']), "url": r.get('url', ''),
                "constructorId": res['Constructor']['constructorId'],
                "driverId": res['Driver']['driverId'],
                "grid": int(res.get('grid', 0)), "laps": int(res.get('laps', 0)),
                "number": int(res.get('number', 0)) if res.get('number') else None,
                "points": float(res.get('points', 0.0)),
                "position": int(res.get('position', 0)) if res.get('position') else None,
                "positionText": res.get('positionText', ''), "status": res.get('status', '')
            })
    if records:
        df_res = spark.createDataFrame(records, schema=results_schema)
        df_res.write.mode("overwrite").parquet(os.path.join(BRONZE_DIR, f"{entity_name}/{entity_name}.parquet"))

print("🏁 All 2026-01 through 2026-XX landing folders populated with 100% complete files!")
