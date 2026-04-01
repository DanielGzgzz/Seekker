#!/bin/bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Define colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error Handling Trap
function error_handler {
    echo -e "\n${RED}[ERROR] An error occurred on line $1. The launch process has stopped.${NC}"
    echo -e "${YELLOW}Please check the error message above, fix the issue, and try running this script again.${NC}"
    exit 1
}
trap 'error_handler $LINENO' ERR

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  IGNITING SYNTHETIC MARKET ANALYSIS AGENT          ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 could not be found.${NC}"
    echo "Please install it on your Ubuntu machine by running:"
    echo -e "${YELLOW}sudo apt update && sudo apt install python3 python3-venv${NC}"
    exit 1
fi

# Ensure python3-venv is available before attempting to create the venv
if ! python3 -c "import venv" &> /dev/null; then
    echo -e "${RED}[ERROR] Python 'venv' module is missing.${NC}"
    echo "Please install it on your Ubuntu machine by running:"
    echo -e "${YELLOW}sudo apt update && sudo apt install python3-venv${NC}"
    exit 1
fi

# Set up virtual environment
VENV_DIR=".venv_agent"
ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"

if [ -f "$ACTIVATE_SCRIPT" ]; then
    echo -e "\n${GREEN}[1/3] Virtual environment detected and functional. Using it.${NC}"
else
    if [ -d "$VENV_DIR" ]; then
        echo -e "\n${YELLOW}[!] Virtual environment directory exists but is corrupted (missing bin/activate). Recreating...${NC}"
        rm -rf "$VENV_DIR"
    fi
    echo -e "\n${GREEN}[1/3] Creating Python virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$ACTIVATE_SCRIPT"

# Install requirements
echo -e "\n${GREEN}[2/3] Installing dependencies...${NC}"
# Install core AI, math, and web dashboard libraries
pip install --quiet google-cloud-aiplatform==1.45.0 numpy==1.26.4 streamlit==1.32.2 pandas==2.2.1 plotly==5.19.0

echo -e "\n${GREEN}[3/3] Launching Web Dashboard...${NC}"

# Check if GCP credentials exist. If not, warn user.
if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && ! gcloud auth print-access-token &> /dev/null; then
    echo -e "\n⚠️  No Google Cloud credentials detected."
    echo "The dashboard will default to MOCK MODE."
    echo "To run with real AI, please authenticate using: gcloud auth application-default login"
fi

# Launch the Streamlit app. It will automatically open the browser.
streamlit run streamlit_app.py
