# .github/ — CI/CD

## Workflow: `workflows/deploy.yml` ("Deploy to EC2")

Runs on every push to `main` and can be started manually (`workflow_dispatch`).

Steps:
1. Check out the code and configure AWS credentials from the repository secrets
   `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (region `us-east-1`).
2. Find the running EC2 instance tagged `Name=LPL-Demo-Final` and terminate it.
3. Launch a new `t3.medium` instance with a startup script that clones this repository,
   installs `requirements.txt` and runs `start.sh` (backend on port 8000, frontend on 8080).
4. Wait for the app to start and print a deployment summary.

## Result

The official team instance is **<http://98.89.13.40:8080>**.

Each deploy replaces the instance, so its public IP can change. Update the link in the
root README if it does.

## Notes

- The deploy depends on resources in the account that owns the secrets (AMI, security
  group `sg-0dd72a92e5600310f`, instance profile `LPL-App-EC2-Profile`). It will not run
  in a different AWS account without changing those values.
- The instance profile supplies Bedrock and DynamoDB access, so no keys are stored on
  the instance.
- Port 8080 is open over plain HTTP and the app has no login. Restrict access before
  using real client data.
- A deploy interrupts the site for a few minutes while the new instance boots.
