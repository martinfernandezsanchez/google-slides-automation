#!/bin/bash

# Google Slides Automation Service Deployment Script
# Deploys to GCP Cloud Run in the monk-tagging project

set -e

# Configuration
PROJECT_ID="monk-tagging"
SERVICE_NAME="slides-automation"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Google Slides Automation Service to GCP"
echo "Project: ${PROJECT_ID}"
echo "Service: ${SERVICE_NAME}"
echo "Region: ${REGION}"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Set the project
echo "📋 Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and deploy using Cloud Build
echo "🏗️ Building and deploying with Cloud Build..."
gcloud builds submit --config cloudbuild.yaml .

# Get the service URL
echo "🔍 Getting service URL..."
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(status.url)")

echo ""
echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: ${SERVICE_URL}"
echo ""
echo "📋 Available endpoints:"
echo "   • Health check: ${SERVICE_URL}/health"
echo "   • Service info: ${SERVICE_URL}/"
echo "   • Metrics: ${SERVICE_URL}/metrics"
echo "   • Create presentation: ${SERVICE_URL}/presentations/create"
echo ""
echo "🔧 To view logs:"
echo "   gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}' --limit=50"
echo ""
echo "🔧 To update the service:"
echo "   ./deploy.sh" 