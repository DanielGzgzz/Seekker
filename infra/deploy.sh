#!/bin/bash

# Configuration Variables
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
DB_INSTANCE_NAME="synthetic-db-instance"
DB_NAME="synthetic_db"
DB_USER="postgres"
DB_PASS="secure_password_here"
API_SERVICE_NAME="synthetic-api"
GENERATOR_JOB_NAME="profile-generator"
API_GATEWAY_NAME="synthetic-api-gateway"
API_CONFIG_NAME="synthetic-api-config"
OPENAPI_SPEC="openapi2-run.yaml"

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
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

# ==========================================
# Task 2: Cloud SQL Setup
# ==========================================
echo "Setting up Cloud SQL..."

# Create Cloud SQL PostgreSQL instance
gcloud sql instances create $DB_INSTANCE_NAME \
    --database-version=POSTGRES_15 \
    --cpu=2 \
    --memory=8GB \
    --region=$REGION \
    --root-password=$DB_PASS \
    --edition=ENTERPRISE

# Create the database
gcloud sql databases create $DB_NAME \
    --instance=$DB_INSTANCE_NAME

# NOTE: You will need to connect to the database and run db_setup.sql manually
# gcloud sql connect $DB_INSTANCE_NAME --user=postgres < db_setup.sql

# ==========================================
# Task 1: Cloud Run Job (Generator)
# ==========================================
echo "Deploying Generator Cloud Run Job..."

# Build and deploy the generator job
gcloud run jobs deploy $GENERATOR_JOB_NAME \
    --source . \
    --region=$REGION \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME,DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$DB_INSTANCE_NAME" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME" \
    --project=$PROJECT_ID \
    --command="" --args="" # Clear existing args if any, relying on Dockerfile.generator

# Use gcloud builds submit for the generator to explicitly use the Dockerfile
gcloud builds submit --tag gcr.io/$PROJECT_ID/$GENERATOR_JOB_NAME -f Dockerfile.generator .
gcloud run jobs update $GENERATOR_JOB_NAME --image gcr.io/$PROJECT_ID/$GENERATOR_JOB_NAME --region=$REGION

# ==========================================
# Task 3 & 4: Cloud Run API Service
# ==========================================
echo "Deploying API Cloud Run Service..."

# Use gcloud builds submit for the API to explicitly use the Dockerfile
gcloud builds submit --tag gcr.io/$PROJECT_ID/$API_SERVICE_NAME -f Dockerfile.api .

# Deploy the FastAPI service
gcloud run deploy $API_SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$API_SERVICE_NAME \
    --region=$REGION \
    --no-allow-unauthenticated \
    --set-env-vars="PROJECT_ID=$PROJECT_ID,REGION=$REGION,DB_USER=$DB_USER,DB_PASS=$DB_PASS,DB_NAME=$DB_NAME,DB_HOST=/cloudsql/$PROJECT_ID:$REGION:$DB_INSTANCE_NAME,STRIPE_WEBHOOK_SECRET=your_stripe_secret,STRIPE_API_KEY=your_stripe_api_key" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:$DB_INSTANCE_NAME"

# Get the URL of the deployed Cloud Run service
API_URL=$(gcloud run services describe $API_SERVICE_NAME --region=$REGION --format 'value(status.url)')

# ==========================================
# Task 3: API Gateway Setup
# ==========================================
echo "Setting up API Gateway..."

# Create an OpenAPI spec for API Gateway (requires manual creation of openapi2-run.yaml if not present)
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

# Create API Gateway API
gcloud api-gateway apis create $API_SERVICE_NAME --project=$PROJECT_ID

# Get project number for default compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Create API Gateway Config
gcloud api-gateway api-configs create $API_CONFIG_NAME \
    --api=$API_SERVICE_NAME \
    --openapi-spec=$OPENAPI_SPEC \
    --project=$PROJECT_ID \
    --backend-auth-service-account=$SERVICE_ACCOUNT

# Create the Gateway
gcloud api-gateway gateways create $API_GATEWAY_NAME \
    --api=$API_SERVICE_NAME \
    --api-config=$API_CONFIG_NAME \
    --location=$REGION \
    --project=$PROJECT_ID

echo "Deployment complete! API Gateway URL:"
gcloud api-gateway gateways describe $API_GATEWAY_NAME \
    --location=$REGION \
    --project=$PROJECT_ID \
    --format="value(defaultHostname)"
