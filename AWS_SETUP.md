# 🔧 AWS Account Setup

> **Not required for the local mock demo.** The app runs fully offline with
> `BEDROCK_MOCK_MODE=true` (the default). Only follow this guide when you're
> ready to generate drafts with real Amazon Bedrock, or deploy the Lambda
> Mock Gate to AWS.

## Step 1: Enable Bedrock Model Access

### 1. Open AWS Bedrock Console
```
https://console.aws.amazon.com/bedrock/
```

### 2. Navigate to Model Access
- In the left sidebar, click **"Model access"**
- Or go directly: https://console.aws.amazon.com/bedrock/home#/modelaccess

### 3. Request Model Access
Click **"Manage model access"** or **"Edit"**

**Enable this model:**
- ✅ **Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`)

### 4. Submit Request
- Check the box for the model
- Click **"Request model access"** or **"Save changes"**
- Wait 1-2 minutes for approval (usually instant)

### 5. Verify Access
- Status should show **"Access granted"** with a green checkmark

## Step 2: Configure AWS CLI

### Check Current Configuration
```bash
aws sts get-caller-identity
```

### If Not Configured
```bash
aws configure
```

Enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `us-east-1` (recommended for Bedrock)
- Output format: `json`

### Test Bedrock Access
```bash
aws bedrock list-foundation-models --region us-east-1

aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --region us-east-1 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}' \
  /tmp/response.json

cat /tmp/response.json
```

## Step 3: IAM Permissions

For running the backend locally against real Bedrock, your user/role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```

For deploying the Lambda Mock Gate via `infra/setup.sh`, your user/role also needs
permissions to create Lambda functions, IAM roles, and CloudFormation stacks
(an admin user is simplest for hackathon purposes).

## Step 4: Region Considerations

**Recommended Region: us-east-1 (N. Virginia)**

Claude 3.5 Sonnet is available in:
- us-east-1 (N. Virginia)
- us-west-2 (Oregon)
- eu-west-1 (Ireland)
- ap-southeast-1 (Singapore)
- ap-northeast-1 (Tokyo)

Update `AWS_REGION` / `BEDROCK_MODEL_ID` in your `.env` (see `.env.example`) if
using a different region.

## Troubleshooting

### "AccessDeniedException: User is not authorized"
→ Enable model access in Bedrock console (Step 1)

### "ValidationException: The provided model identifier is invalid"
→ Check model ID matches exactly: `anthropic.claude-3-5-sonnet-20241022-v2:0`

### "ThrottlingException: Rate exceeded"
→ Bedrock has usage quotas. For hackathon, request a quota increase via
Service Quotas → AWS Bedrock, or continue after a cooldown period.

## Cost Management

### Set Billing Alert
1. Go to AWS Billing Dashboard
2. Set up a billing alarm (e.g., $25 threshold)

### Cost Estimates
- Claude 3.5 Sonnet: $3 per million input tokens, $15 per million output tokens
- Lambda Function URL: Free tier covers hackathon usage

**Hackathon estimate:** <$10 total for dozens of draft generations

## Ready to Deploy!

Once AWS is configured:
```bash
cd infra
./setup.sh
```

Then follow [QUICKSTART.md](QUICKSTART.md) to point the frontend at the
deployed Lambda Function URL.
