#!/bin/bash

echo "============================================================"
echo "        STARTING F1 ANALYTICS STREAMLIT DASHBOARD"
echo "============================================================"

APP_PATH="/Users/manoharazalki/F1-Analytics/dashboard/app.py"
LOG_FILE="/Users/manoharazalki/F1-Analytics/scripts/dashboard.log"

echo "▶ Running Streamlit app at: $APP_PATH"
echo "▶ Logging output to: $LOG_FILE"
echo "------------------------------------------------------------"

streamlit cache clear

streamlit run "$APP_PATH" 2>&1 | tee "$LOG_FILE"

echo "------------------------------------------------------------"
echo "        ✔ STREAMLIT DASHBOARD EXECUTION FINISHED"
echo "------------------------------------------------------------"
