#!/bin/bash

# ==============================================================================
# Ubuntu Interactive Setup Guide for Synthetic SaaS Pipeline on GCP
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
# Treat unset variables as an error when substituting.
# The return value of a pipeline is the status of the last command to exit with a non-zero status.
set -eo pipefail

# Define Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Error Handling Trap
function error_handler {
    echo -e "\n${RED}[ERROR] An error occurred on line $1. The deployment has stopped.${NC}"
    echo -e "${YELLOW}Please check the error message above, fix the issue, and try running this script again.${NC}"
    exit 1
}
trap 'error_handler $LINENO' ERR

# Function to pause and wait for user acknowledgment
function pause() {
   read -p "Press [Enter] key to continue..."
}

clear
echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}  Welcome to the Ubuntu Interactive Setup Guide for your Serverless Backend  ${NC}"
echo -e "${CYAN}==============================================================================${NC}"
echo -e "This script will guide you through setting up your Google Cloud infrastructure:"
echo -e "  - Cloud SQL for PostgreSQL (with pgvector)"
echo -e "  - Cloud Run Job (Data Generator using Vertex AI)"
echo -e "  - Cloud Run API Service (FastAPI + Stripe Integration)"
echo -e "  - Google API Gateway"
echo ""
echo -e "${YELLOW}Before you begin, ensure you have:${NC}"
echo -e "  1. Installed the Google Cloud CLI (gcloud) on your Ubuntu machine."
echo -e "  2. Run 'gcloud auth login' to authenticate your user account."
echo -e "  3. Selected an active Google Cloud Project with Billing Enabled."
echo -e "  4. Your Stripe API Key and Webhook Secret ready."
echo ""
pause
clear

# ==========================================
# Phase 1: Configuration Input
# ==========================================
echo -e "${GREEN}--- Phase 1: Configuration ---${NC}"

# Default values
DEFAULT_REGION="us-central1"
DEFAULT_DB_USER="postgres"
DEFAULT_DB_NAME="synthetic_db"
DEFAULT_DB_INSTANCE_NAME="synthetic-db-instance"

echo -e "Please provide the required configuration parameters."
echo -e "Press Enter to accept default values shown in brackets [].\n"

# 1. GCP Project ID
read -p "Enter your Google Cloud Project ID: " PROJECT_ID
while [[ -z "$PROJECT_ID" ]]; do
    echo -e "${RED}Project ID cannot be empty.${NC}"
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
done

# 2. GCP Region
read -p "Enter the Google Cloud Region [$DEFAULT_REGION]: " REGION
REGION=${REGION:-$DEFAULT_REGION}

# 3. Database Instance Name
read -p "Enter a name for the Cloud SQL instance [$DEFAULT_DB_INSTANCE_NAME]: " DB_INSTANCE_NAME
DB_INSTANCE_NAME=${DB_INSTANCE_NAME:-$DEFAULT_DB_INSTANCE_NAME}

# 4. Database Name
read -p "Enter the Database Name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}

# 5. Database User
read -p "Enter the Database Username [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}

# 6. Database Password
read -s -p "Enter a Secure Password for the Database User: " DB_PASS
echo ""
while [[ -z "$DB_PASS" ]]; do
    echo -e "${RED}Database password cannot be empty.${NC}"
    read -s -p "Enter a Secure Password for the Database User: " DB_PASS
    echo ""
done

# 7. Stripe API Key
read -s -p "Enter your Stripe Secret API Key (sk_test_...): " STRIPE_API_KEY
echo ""
while [[ -z "$STRIPE_API_KEY" ]]; do
    echo -e "${RED}Stripe API Key cannot be empty.${NC}"
    read -s -p "Enter your Stripe Secret API Key (sk_test_...): " STRIPE_API_KEY
    echo ""
done

# 8. Stripe Webhook Secret
read -s -p "Enter your Stripe Webhook Secret (whsec_...): " STRIPE_WEBHOOK_SECRET
echo ""
while [[ -z "$STRIPE_WEBHOOK_SECRET" ]]; do
    echo -e "${RED}Stripe Webhook Secret cannot be empty.${NC}"
    read -s -p "Enter your Stripe Webhook Secret (whsec_...): " STRIPE_WEBHOOK_SECRET
    echo ""
done

# Service Names (Internal)
API_SERVICE_NAME="synthetic-api"
GENERATOR_JOB_NAME="profile-generator"
API_GATEWAY_NAME="synthetic-api-gateway"
API_CONFIG_NAME="synthetic-api-config"
OPENAPI_SPEC="openapi2-run.yaml"

echo -e "\n${BLUE}Configuration Collected Successfully.${NC}"
echo -e "Project ID: ${YELLOW}$PROJECT_ID${NC}"
echo -e "Region: ${YELLOW}$REGION${NC}"
echo -e "DB Instance: ${YELLOW}$DB_INSTANCE_NAME${NC}"
echo -e "Stripe Keys: ${YELLOW}[Provided and Masked]${NC}"
echo ""
read -p "Are you ready to begin the deployment? Type 'yes' to proceed: " confirm
if [[ "$confirm" != "yes" ]]; then
    echo -e "${RED}Deployment cancelled by user.${NC}"
    exit 0
fi

clear

# ==========================================
# Phase 2: GCP Setup & API Enabling
# ==========================================
echo -e "${GREEN}--- Phase 2: Google Cloud Initial Setup ---${NC}"
echo "Setting current project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

echo "Enabling necessary Google Cloud APIs. This might take a few minutes..."
gcloud services enable \
    compute.googleapis.com \
    sqladmin.googleapis.com \
    run.googleapis.com \
    vpcaccess.googleapis.com \
    servicenetworking.googleapis.com \
    aiplatform.googleapis.com \
    apigateway.googleapis.com \
    apikeys.googleapis.com \
    servicecontrol.googleapis.com \
    cloudbuild.googleapis.com

echo -e "${BLUE}APIs enabled successfully.${NC}\n"

# ==========================================
# Phase 3: Cloud SQL Deployment
# ==========================================
echo -e "${GREEN}--- Phase 3: Cloud SQL Setup ---${NC}"
echo "Checking if Cloud SQL instance '$DB_INSTANCE_NAME' already exists..."

if gcloud sql instances describe $DB_INSTANCE_NAME &>/dev/null; then
    echo -e "${YELLOW}Instance '$DB_INSTANCE_NAME' already exists. Skipping creation.${NC}"
else
    echo "Creating Cloud SQL PostgreSQL instance '$DB_INSTANCE_NAME'..."
    gcloud sql instances create $DB_INSTANCE_NAME \
        --database-version=POSTGRES_15 \
        --cpu=2 \
        --memory=8GB \
        --region=$REGION \
        --root-password="$DB_PASS" \
        --edition=ENTERPRISE
fi

echo "Creating database '$DB_NAME'..."
# Ignore error if DB already exists
gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE_NAME || true

echo -e "${BLUE}Cloud SQL setup completed.${NC}\n"

# ==========================================
# Phase 4: Deploy Cloud Run Job (Generator)
# ==========================================
echo -e "${GREEN}--- Phase 4: Deploying Generator Cloud Run Job ---${NC}"
echo "Building and deploying the generator job using Dockerfile.generator..."

gcloud builds submit --tag gcr.io/$PROJECT_ID/$GENERATOR_JOB_NAME -f Dockerfile.generator .

gcloud run jobs create $GENERATOR_JOB_NAME \
    --image gcr.io/$PROJECT_ID/$GENERATOR_JOB_NAME \
    --region=$REGION \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME,DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$DB_INSTANCE_NAME" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME" || \
gcloud run jobs update $GENERATOR_JOB_NAME \
    --image gcr.io/$PROJECT_ID/$GENERATOR_JOB_NAME \
    --region=$REGION \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME,DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$DB_INSTANCE_NAME" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME"

echo -e "${BLUE}Generator Job deployed successfully.${NC}\n"

# ==========================================
# Phase 5: Deploy Cloud Run API Service
# ==========================================
echo -e "${GREEN}--- Phase 5: Deploying Cloud Run API Service ---${NC}"
echo "Building and deploying the FastAPI service using Dockerfile.api..."

gcloud builds submit --tag gcr.io/$PROJECT_ID/$API_SERVICE_NAME -f Dockerfile.api .

gcloud run deploy $API_SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$API_SERVICE_NAME \
    --region=$REGION \
    --no-allow-unauthenticated \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME,DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$DB_INSTANCE_NAME,STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET,STRIPE_API_KEY=$STRIPE_API_KEY" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME"

# Get the URL of the deployed Cloud Run service
API_URL=$(gcloud run services describe $API_SERVICE_NAME --region=$REGION --format 'value(status.url)')
echo -e "${BLUE}Internal API Service URL: ${API_URL}${NC}\n"

# ==========================================
# Phase 6: API Gateway Setup
# ==========================================
echo -e "${GREEN}--- Phase 6: API Gateway Setup ---${NC}"
echo "Generating OpenAPI Specification..."

cat <<EOF > $OPENAPI_SPEC
swagger: '2.0'
info:
  title: Synthetic Market API
  description: API Gateway for Synthetic Market Data
  version: 1.0.0
schemes:
  - https
produces:
  - application/json
paths:
  /generate:
    post:
      summary: Generate Market Report
      operationId: generate
      x-google-backend:
        address: $API_URL/generate
      security:
        - api_key: []
      responses:
        '200':
          description: A successful response
  /analyze_product:
    post:
      summary: Multimodal Product Analysis
      operationId: analyze_product
      x-google-backend:
        address: $API_URL/analyze_product
      security:
        - api_key: []
      responses:
        '200':
          description: A successful response
  /checkout:
    post:
      summary: Create Stripe Checkout Session
      operationId: checkout
      x-google-backend:
        address: $API_URL/checkout
      responses:
        '200':
          description: A successful response
  /status/{session_id}:
    get:
      summary: Check Payment Status
      operationId: status
      x-google-backend:
        address: $API_URL/status/{session_id}
      parameters:
        - name: session_id
          in: path
          required: true
          type: string
      responses:
        '200':
          description: A successful response
  /webhook:
    post:
      summary: Stripe Webhook
      operationId: webhook
      x-google-backend:
        address: $API_URL/webhook
      responses:
        '200':
          description: Webhook processed
securityDefinitions:
  api_key:
    type: apiKey
    name: key
    in: query
EOF

echo "Creating API Gateway definitions..."
# Create API (Ignore if exists)
gcloud api-gateway apis create $API_SERVICE_NAME --project=$PROJECT_ID || true

# Get project number for default compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Creating API Config ($API_CONFIG_NAME)..."
gcloud api-gateway api-configs create $API_CONFIG_NAME \
    --api=$API_SERVICE_NAME \
    --openapi-spec=$OPENAPI_SPEC \
    --project=$PROJECT_ID \
    --backend-auth-service-account=$SERVICE_ACCOUNT

echo "Creating API Gateway. This may take a few minutes..."
gcloud api-gateway gateways create $API_GATEWAY_NAME \
    --api=$API_SERVICE_NAME \
    --api-config=$API_CONFIG_NAME \
    --location=$REGION \
    --project=$PROJECT_ID

GATEWAY_URL=$(gcloud api-gateway gateways describe $API_GATEWAY_NAME --location=$REGION --project=$PROJECT_ID --format="value(defaultHostname)")

echo -e "${BLUE}API Gateway deployed successfully.${NC}\n"

# ==========================================
# Final Summary and Manual Steps
# ==========================================
clear
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}                 DEPLOYMENT COMPLETED SUCCESSFULLY!                           ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "Your API Gateway is live at:"
echo -e "${CYAN}https://${GATEWAY_URL}${NC}"
echo ""
echo -e "Your Stripe Webhook URL is:"
echo -e "${CYAN}https://${GATEWAY_URL}/webhook${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: MANUAL POST-DEPLOYMENT STEP REQUIRED${NC}"
echo -e "You must initialize the database schema before running the generator job or the API."
echo -e "To do this, execute the following command from your terminal:"
echo ""
echo -e "  ${CYAN}gcloud sql connect $DB_INSTANCE_NAME --user=$DB_USER < db_setup.sql${NC}"
echo ""
echo -e "Note: You will be prompted for your database password (${DB_PASS})."
echo ""
echo -e "${YELLOW}After initializing the database, you can run your first synthetic data generation batch:${NC}"
echo -e "  ${CYAN}gcloud run jobs execute $GENERATOR_JOB_NAME --region=$REGION${NC}"
echo ""
echo -e "Thank you for using the Ubuntu Interactive Setup Guide!"
