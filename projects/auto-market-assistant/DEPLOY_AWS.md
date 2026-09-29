# AWS deployment — execution checklist

The infrastructure code is already in this repository. These are the remaining account-specific steps.

## 1. Bootstrap the AWS account

Open AWS CloudShell and run:

```bash
export AWS_REGION=ca-central-1
bash projects/auto-market-assistant/infra/bootstrap_aws.sh
```

The script creates:
- a private versioned S3 artifact bucket;
- an ECR repository;
- GitHub's OIDC trust in AWS if it does not already exist;
- a GitHub Actions deployment role.

Keep the printed values.

## 2. Upload artifacts

The API expects:

```text
processed/vehicles_clean.parquet
processed/review_documents.parquet
artifacts/price_model.cbm
artifacts/model_improvement_metrics.json
artifacts/review_index.faiss
artifacts/rag_metrics.json
```

From the directory containing the saved Part 1 and Part 2 artifacts:

```bash
python projects/auto-market-assistant/src/upload_artifacts_to_s3.py \
  --bucket YOUR_BUCKET
```

## 3. Build the first container

```bash
aws ecr get-login-password --region YOUR_REGION \
| docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com

docker build \
  -t auto-market-assistant:latest \
  projects/auto-market-assistant

docker tag auto-market-assistant:latest \
  YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com/auto-market-assistant:latest

docker push \
  YOUR_ACCOUNT.dkr.ecr.YOUR_REGION.amazonaws.com/auto-market-assistant:latest
```

## 4. Create App Runner

Deploy `infra/apprunner-template.yaml` with:
- ImageIdentifier = the ECR image ending in `:latest`
- ArtifactBucketName = the S3 bucket from step 1

The default cloud deployment uses retrieval-backed answers with deterministic source fallback. The portfolio's precomputed Qwen outputs remain available through the static JSON demo. GPU Qwen serving can be added separately if required.

## 5. Configure GitHub repository variables

Add these GitHub Actions variables:
- AWS_REGION
- AWS_ROLE_ARN
- ECR_REPOSITORY
- APP_RUNNER_SERVICE_ARN

After those exist, merges to main can build the Docker image and trigger App Runner automatically.

## 6. Verify

```bash
curl https://YOUR_APP_RUNNER_URL/health
```

Expected:

```json
{
  "status": "ok",
  "service": "auto-market-assistant",
  "generation_enabled": false
}
```

Then test `POST /predict-price` and `POST /ask`.

## 7. Portfolio connection

Keep `auto-market-demo-data.json` as the reliable static fallback. Once the App Runner URL is stable, the portfolio JavaScript can try the live API first and fall back to the versioned JSON when the API is unavailable.
