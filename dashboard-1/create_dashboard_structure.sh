#!/bin/bash

# Create base dashboard directory
mkdir -p dashboard/pages

# Create main app file
touch dashboard/app.py

# Create utility file
touch dashboard/utils.py

# Create pages
touch dashboard/pages/Driver_Performance.py
touch dashboard/pages/Constructor_Dominance.py
touch dashboard/pages/Track_and_Region_Insights.py
touch dashboard/pages/Season_Analytics.py
touch dashboard/pages/Predictive_Insights.py

echo "Dashboard structure created successfully!"
