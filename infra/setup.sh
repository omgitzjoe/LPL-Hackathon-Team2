#!/bin/bash
# Deploy the Lambda Function URL (Mock Gate) infrastructure using AWS SAM.
#
# Requires: AWS SAM CLI (https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
#           AWS CLI configured with credentials that can create Lambda/IAM resources
#           Bedrock model access enabled for the chosen model (see ../AWS_SETUP.md)

set -e

STACK_NAME="lpl-delegation-assistant"
REGION="${AWS_REGION:-us-east-1}"

echo "🚀 Building and deploying LPL Delegation Assistant backend..."
echo "Region: $REGION"
echo ""

sam build --template-file template.yaml

sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset

echo ""
echo "✅ Deployed. Fetching Function URL..."
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output table

echo ""
echo "💡 Set BACKEND_URL to the FunctionUrl above and re-run the Streamlit frontend:"
echo "   BACKEND_URL=https://xxxx.lambda-url.$REGION.on.aws/ streamlit run frontend/app.py"
