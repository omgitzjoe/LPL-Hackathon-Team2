# GitHub Actions CI/CD Setup

This repository uses GitHub Actions to automatically deploy the LPL Delegation Assistant to EC2 whenever code is pushed to the `main` branch.

## How It Works

1. **Push to main** → GitHub Actions workflow triggers
2. **Finds old instance** tagged with `LPL-Demo-Final`
3. **Terminates old instance** gracefully
4. **Launches new instance** with latest code from GitHub
5. **Waits for startup** and verifies the app is responding
6. **Reports URL** in the Actions log

## Initial Setup (One-Time)

### Step 1: Add AWS Credentials to GitHub Secrets

1. Go to your GitHub repository: https://github.com/omgitzjoe/LPL-Hackathon-Team2
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

**Secret 1:**
- Name: `AWS_ACCESS_KEY_ID`
- Value: *(your AWS access key ID — get from your team lead or AWS Console)*

**Secret 2:**
- Name: `AWS_SECRET_ACCESS_KEY`
- Value: *(your AWS secret access key — get from your team lead or AWS Console)*

### Step 2: Commit and Push the Workflow

```bash
git add .github/workflows/deploy.yml .github/DEPLOYMENT.md
git commit -m "Add GitHub Actions CI/CD pipeline for auto-deployment"
git push origin main
```

### Step 3: Watch the Deployment

1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. Watch the deployment progress
4. Get the new public URL from the "Deployment summary" step

## Usage

### Automatic Deployment
Just push to main:
```bash
git add .
git commit -m "Your changes"
git push origin main
```

The workflow will automatically:
- Terminate the old EC2 instance
- Launch a new one with your latest code
- Report the new public IP in the Actions log

### Manual Deployment
1. Go to **Actions** → **Deploy to EC2**
2. Click **Run workflow**
3. Select branch `main`
4. Click **Run workflow**

## Finding Your Live URL

After each deployment:
1. Go to **Actions** → latest workflow run
2. Expand the **Deployment summary** step
3. Copy the URL (format: `http://<new-ip>:8080`)

Or check AWS Console:
- EC2 → Instances
- Find instance tagged `LPL-Demo-Final`
- Use its public IP: `http://<public-ip>:8080`

## Deployment Time

- Total: ~6-7 minutes
  - Terminate old instance: 30 seconds
  - Launch new instance: 1 minute
  - Install dependencies: 2-3 minutes
  - Application startup: 2-3 minutes
  - Health check: 30 seconds

## What Gets Deployed

The workflow deploys:
- Latest code from the `main` branch at the specific commit SHA
- Backend (FastAPI + Bedrock) on port 8000
- Frontend (Streamlit UI) on port 8080
- Tags the instance with the Git commit SHA for traceability

## Troubleshooting

**Workflow fails at "Wait for application startup":**
- Check EC2 console logs: EC2 → Instances → Select instance → Actions → Monitor and troubleshoot → Get system log
- The application might need more time to start (increase sleep time in workflow)

**"Instance not found" error:**
- Make sure you're deploying to the correct AWS account
- Check that the security group `sg-0dd72a92e5600310f` and IAM profile `LPL-App-EC2-Profile` exist

**Changes not reflected after deployment:**
- Verify your changes were pushed to the `main` branch
- Check that the workflow completed successfully (green checkmark)
- Git commit SHA on the EC2 instance tag should match your latest commit

## Cost Optimization

The workflow terminates the old instance before launching a new one, so you only pay for one EC2 instance at a time. Each deployment creates a fresh instance from scratch.

To stop all instances and stop costs:
```bash
aws ec2 terminate-instances --instance-ids $(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=LPL-Demo-Final" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
```
