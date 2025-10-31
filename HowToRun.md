# Quick Start Guide

## 1. Setup Virtual Environment

```bash
# Create venv
python3 -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Prepare Data

Download CSV files from and extract to:

```
data/tripdata/*.csv
```

**Example:**
```
data/tripdata/202301-divvy-tripdata.csv
data/tripdata/202302-divvy-tripdata.csv
...
```

## 3. Run Application

```bash
# Full pipeline (init DB + ETL + dashboard)
python main.py

# Skip ETL if already done
python main.py --skip-etl

# ETL only (no dashboard)
python main.py --etl-only
```
