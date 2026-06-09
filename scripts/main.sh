#!/bin/bash

rm -rf *.log

echo "------------------------------------------------------------"
echo " Clearing Streamlit Cache "
echo "------------------------------------------------------------"
streamlit cache clear

echo "------------------------------------------------------------"
echo " Running F1 Pipeline "
echo "------------------------------------------------------------"
sh run_pipeline.sh >> pipeline.log

echo "------------------------------------------------------------"
echo " Starting Dashboard "
echo "------------------------------------------------------------"
sh run_dashboard.sh >> dashboard.log
