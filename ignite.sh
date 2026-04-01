#!/bin/bash

# Exit on error
set -e

# Define colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  IGNITING SYNTHETIC MARKET ANALYSIS AGENT          ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 could not be found. Please install it on your Ubuntu machine:"
    echo "sudo apt update && sudo apt install python3 python3-venv"
    exit 1
fi

# Set up virtual environment
VENV_DIR=".venv_agent"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "\n${GREEN}[1/3] Creating Python virtual environment...${NC}"
    python3 -m venv $VENV_DIR
else
    echo -e "\n${GREEN}[1/3] Virtual environment already exists. Using it.${NC}"
fi

# Activate virtual environment
source $VENV_DIR/bin/activate

# Install requirements
echo -e "\n${GREEN}[2/3] Installing dependencies...${NC}"
# Install core AI, math, and web dashboard libraries
pip install --quiet google-cloud-aiplatform==1.45.0 numpy==1.26.4 streamlit==1.32.2 pandas==2.2.1 plotly==5.19.0

echo -e "\n${GREEN}[3/3] Launching Web Dashboard...${NC}"

# Check if GCP credentials exist. If not, warn user.
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ] && ! gcloud auth print-access-token &> /dev/null; then
    echo -e "\n⚠️  No Google Cloud credentials detected."
    echo "The dashboard will default to MOCK MODE."
    echo "To run with real AI, please authenticate using: gcloud auth application-default login"
fi

# Launch the Streamlit app. It will automatically open the browser.
streamlit run streamlit_app.py
