#!/bin/bash

# Create base dashboard directory
mkdir -p dashboard/sections

# Create main app and utils files
touch dashboard/app.py
touch dashboard/utils.py

# Create section files
touch dashboard/sections/rq1_driver_constructor.py
touch dashboard/sections/rq2_race_outcomes.py
touch dashboard/sections/rq3_circuit_geography.py
touch dashboard/sections/rq4_sprint_race.py
touch dashboard/sections/rq5_cross_dataset.py
touch dashboard/sections/executive_summary.py

echo "Dashboard structure with sections created successfully!"
