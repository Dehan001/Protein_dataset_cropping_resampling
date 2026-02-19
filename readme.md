# Protein Cropping Automation

## Overview
This project automates protein structure cropping and analysis using PDB and EMD (Electron Microscopy Database) data.

## Workflow (cropping.py)

1. **Data Dictionary Creation**
    - Loads PDB structures and corresponding EMD maps
    - Reads input parameters from `input.txt`
    - Fetches EMD resolution from the database

2. **Structure Alignment**
    - Fits PDB structures to EMD maps using ChimeraX commands

3. **Chain Separation & Cropping**
    - Separates individual chains from the fitted structure
    - Uses `volume cover` command to generate bounding boxes around each chain

4. **Correlation Calculation**
    - Computes correlation metrics between PDB and EMD data
    - Requires resolution data for accurate calculations

## Current Limitations

- Resolution data is fetched from the internet multiple times during execution
- **TODO:** Implement caching to fetch resolution once and reuse throughout the analysis

## Requirements
- ChimeraX
- Python 3.x
- Input file: `input.txt`
