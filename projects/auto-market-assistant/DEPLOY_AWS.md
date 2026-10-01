# AWS deployment — ECS Express Mode

The project is deployed as a Dockerized FastAPI service on Amazon ECS Express Mode with artifacts stored in S3 and the image stored in ECR.

## Current live service

`https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws`

Health check:

```bash
curl https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws/health
```

## Required AWS resources

- private S3 artifact bucket
- ECR repository
- `ecsTaskExecutionRole`
- `ecsInfrastructureRoleForExpressServices`
- `AutoMarketTaskRole` with `s3:GetObject` on the processed/artifact prefixes
- ECS and Application Auto Scaling service-linked roles
- ECS Express Mode service

## Artifact layout

```text
processed/vehicles_clean.parquet
processed/review_documents.parquet
artifacts/price_model.cbm
artifacts/model_improvement_metrics.json
artifacts/review_index.faiss
artifacts/rag_metrics.json
```

## Build and push

```bash
export AWS_REGION=ca-central-1
export ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ECR_REPOSITORY=auto-market-assistant
export ECR_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY"

aws ecr get-login-password --region "$AWS_REGION" \
| docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t "$ECR_URI:latest" projects/auto-market-assistant
docker push "$ECR_URI:latest"
```

## Runtime configuration

The ECS primary container listens on port 8080 and receives:

```text
ARTIFACT_BUCKET=<private S3 bucket>
ARTIFACT_PREFIX=
ENABLE_GENERATION=false
ALLOWED_ORIGINS=https://gnambood.github.io
```

Health path: `/health`

Recommended portfolio deployment size used for the current service:
- CPU: 1024
- memory: 4096 MiB
- architecture: X86_64
- min tasks: 1
- max tasks: 1

## Smoke tests

```bash
curl "$BASE_URL/health"
curl "$BASE_URL/metrics"

curl -X POST "$BASE_URL/predict-price" \
  -H "Content-Type: application/json" \
  -d '{"manufacturer":"ford","model":"f-150","year":2004,"mileage":65000,"condition":"good","fuel":"gas","title_status":"clean","transmission":"automatic","drive":"4wd","vehicle_type":"truck","state":"ca"}'

curl -X POST "$BASE_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"manufacturer":"ford","model":"f-150","year":2004,"question":"What do owners mention about reliability and common problems?","k":5}'
```

## GitHub Actions variables

For automatic deployments, configure repository variables:

- `AWS_REGION`
- `AWS_ROLE_ARN`
- `ECR_REPOSITORY`
- `ECS_EXPRESS_SERVICE_ARN`
- `ARTIFACT_BUCKET`

The deploy workflow uses GitHub OIDC rather than long-lived AWS access keys.

## Portfolio behavior

The website calls the live API first and falls back to verified static data if the AWS request is unavailable. The static fallback should remain in the repository even while the live service is running.
