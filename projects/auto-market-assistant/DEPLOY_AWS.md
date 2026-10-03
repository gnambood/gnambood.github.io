# AWS Architecture & Deployment

This document describes the **actual production deployment** of Auto Market Assistant and clearly separates it from optional/reference infrastructure that also exists in the repository.

## Production status

The application is deployed in **AWS ca-central-1** as a Dockerized FastAPI service on **Amazon ECS Express Mode / AWS Fargate**.

Live API:

```text
https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws
```

Health check:

```bash
curl https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws/health
```

The deployment workflow verifies the active ECS image and confirms the calibrated answerability policy before treating a deployment as successful.

## End-to-end AWS architecture

```text
GitHub Pages
     |
     | HTTPS
     v
AWS-managed ECS ingress
     |
     v
Amazon ECS Express Mode / Fargate
     |
     |-- FastAPI /predict-price
     |      -> CatBoost model
     |
     |-- FastAPI /ask
     |      -> capability/scope guard
     |      -> vehicle-family/year candidate filtering
     |      -> MiniLM question embedding
     |      -> FAISS similarity search
     |      -> calibrated multi-signal answerability gate
     |      -> citation-safe deterministic evidence response
     |
     |-- /catalog
     |-- /metrics
     |-- /health
     |
     v
Amazon S3
     |-- processed vehicle data
     |-- processed owner-review documents
     |-- CatBoost model
     |-- FAISS index
     |-- evaluation metrics
```

The production service deliberately runs with:

```text
ENABLE_GENERATION=false
```

This keeps the live CPU service smaller and predictable. Qwen generation is validated separately in the final research notebook.

## AWS services used

| AWS service | Production role |
|---|---|
| **Amazon ECS Express Mode / Fargate** | Runs the FastAPI container |
| **Amazon ECR** | Stores versioned Docker images |
| **Amazon S3** | Stores processed datasets, models, FAISS index and metrics |
| **AWS IAM** | Task roles, execution roles and GitHub deployment role |
| **AWS STS / GitHub OIDC federation** | Lets GitHub Actions deploy without long-lived AWS keys |
| **AWS-managed HTTPS ingress** | Public HTTPS endpoint for the ECS service |
| **Application Auto Scaling integration** | ECS Express service scaling configuration |

The repository also contains a **SAM/CloudFormation template for an S3-triggered Lambda raw-upload validator**. That template is part of the project infrastructure design, but it is documented separately from the active serving path so the repo does not imply that every reference component is currently deployed.

## Production resources

The current implementation uses:

- private S3 artifact bucket
- ECR repository: `auto-market-assistant`
- ECS Express Mode service: `auto-market-assistant`
- `ecsTaskExecutionRole`
- `ecsInfrastructureRoleForExpressServices`
- `AutoMarketTaskRole`
- GitHub deployment role: `AutoMarketGitHubDeployRole`
- GitHub Actions OIDC provider for `token.actions.githubusercontent.com`

The ECS task role is used for read-only access to the model/data artifacts needed at runtime.

## S3 layout

The serving application expects:

```text
processed/
  vehicles_clean.parquet
  review_documents.parquet

artifacts/
  price_model.cbm
  model_improvement_metrics.json
  review_index.faiss
  rag_metrics.json
```

The final notebook additionally exports evaluation/reproducibility files such as:

```text
answerability_policy.json
answerability_calibration.csv
final_validation.json
```

The production API packages the validated answerability policy with the application image so the live service and CI smoke test use the same operating point.

## S3 security configuration

`infra/bootstrap_aws.sh` configures the artifact bucket with:

- public ACL blocking
- public policy blocking
- public-bucket restriction
- S3 versioning

The website does **not** read model artifacts directly from S3. The ECS task retrieves them using IAM permissions.

## ECR configuration

The bootstrap script creates the ECR repository when needed and enables:

```text
scanOnPush=true
```

The GitHub Actions deployment publishes two tags:

```text
<git-commit-sha>
latest
```

The commit-SHA tag provides deployment traceability.

## IAM and least-privilege design

### ECS runtime roles

The serving stack uses separate roles for:

- ECS task execution
- ECS infrastructure
- application/task access to S3

The application task role is intended to have only the S3 read permissions needed for the processed/model artifact prefixes.

### GitHub deployment role

GitHub Actions assumes `AutoMarketGitHubDeployRole` through OpenID Connect.

No long-lived AWS access key is required in the repository.

The bootstrap policy grants the deployment workflow the permissions it needs for:

- ECR authentication and image push
- ECS Express service update/describe
- task-definition registration where required
- `iam:PassRole` for the ECS roles used by the service

The trust policy restricts federation to the repository's `main` branch identity.

## CI/CD deployment flow

```text
push to main
    |
    v
GitHub Actions
    |
    |-- obtain temporary AWS credentials through OIDC
    |
    |-- authenticate to Amazon ECR
    |
    |-- docker build
    |
    |-- push SHA tag + latest tag
    |
    |-- update ECS Express Mode service
    |
    |-- wait for new image to become active
    |
    |-- HTTPS /health smoke test
    |
    |-- verify answerability policy
    v
deployment succeeds
```

The workflow is:

```text
.github/workflows/auto-market-deploy.yml
```

A deployment is not considered successful merely because ECS accepted the update. The workflow waits for the requested image revision to become active and then performs a live HTTPS health check.

## Deployment smoke-test contract

The live `/health` endpoint must return:

```json
{
  "status": "ok",
  "service": "auto-market-assistant",
  "generation_enabled": false,
  "answerability_policy": {
    "max_threshold": 0.38,
    "mean_top3_threshold": 0.36,
    "support_threshold": 0.34,
    "min_support_sources": 2
  }
}
```

This verifies that the active ECS revision is running the intended calibrated RAG policy.

## Runtime configuration

The ECS primary container listens on port **8080**.

Production environment variables:

```text
ARTIFACT_BUCKET=<private S3 bucket>
ARTIFACT_PREFIX=
ENABLE_GENERATION=false
ALLOWED_ORIGINS=https://gnambood.github.io
```

Current portfolio-sized service configuration:

```text
CPU:          1024
Memory:       4096 MiB
Architecture: X86_64
Min tasks:    1
Max tasks:    1
Autoscaling:  average CPU target 60%
```

## API smoke tests

```bash
export BASE_URL="https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws"

curl "$BASE_URL/health"
curl "$BASE_URL/metrics"
curl "$BASE_URL/catalog"

curl -X POST "$BASE_URL/predict-price" \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer":"ford",
    "model":"f-150",
    "year":2004,
    "mileage":65000,
    "condition":"good",
    "fuel":"gas",
    "title_status":"clean",
    "transmission":"automatic",
    "drive":"4wd",
    "vehicle_type":"truck",
    "state":"ca"
  }'

curl -X POST "$BASE_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer":"ford",
    "model":"f-150",
    "year":2004,
    "question":"What do owners mention about reliability and common problems?",
    "k":5
  }'
```

## GitHub Actions variables

The repository uses GitHub Actions variables for deploy-time configuration:

- `AWS_REGION`
- `AWS_ROLE_ARN`
- `ECR_REPOSITORY`
- `ECS_EXPRESS_SERVICE_ARN`
- `ARTIFACT_BUCKET`

No AWS secret access key is required for the deployment workflow because authentication is performed through GitHub OIDC.

## Bootstrap automation

`infra/bootstrap_aws.sh` captures the repeatable AWS setup for:

- private/versioned S3 storage
- ECR repository creation
- ECR image scanning
- GitHub OIDC provider
- GitHub deployment IAM role
- deployment-role permissions
- ECS role pass-through permissions

It intentionally stops before blindly recreating the live ECS service. Service creation and artifact upload remain explicit deployment steps.

## Reference data-validation infrastructure

The repository contains:

```text
infra/data-pipeline-template.yaml
lambda/
```

The SAM template defines:

```text
S3 raw/ upload
      |
      v
Lambda validator
      |
      +-- read uploaded object
      +-- apply schema/range validation
      +-- write validation result
```

This represents the project's serverless raw-data validation design. It should be described as **reference/optional infrastructure unless that stack is explicitly deployed**.

## Website resilience

The portfolio browser calls the live ECS API first.

If AWS is unavailable or warming up, the website falls back to a verified static result rather than fabricating browser-side inference.

```text
GitHub Pages
     |
     |-- live request succeeds --> AWS response
     |
     +-- live request fails ----> verified static fallback
```

## Production design decisions

**Why ECS/Fargate?**  
The project needs Python ML dependencies, FAISS, CatBoost and a persistent API process. Containerized ECS serving is a better fit than forcing the inference stack into a small function runtime.

**Why S3?**  
Model and index artifacts are large and should not be committed to Git. S3 provides durable private object storage that the ECS task can access through IAM.

**Why ECR?**  
The deployment is container-based, and ECR provides private image storage integrated with ECS.

**Why GitHub OIDC?**  
It avoids storing long-lived AWS credentials in GitHub while still supporting automated deployment.

**Why generation disabled in production?**  
The portfolio ECS service is CPU-oriented. The validated notebook demonstrates Qwen generation, while the live service prioritizes lower infrastructure cost, predictable startup and deterministic evidence-backed behavior.

## What is deliberately not claimed

The repository does not imply that this is a production commercial SLA.

It also does not claim that the Lambda validation reference stack, custom alerting, or a GPU-hosted Qwen service are active unless explicitly deployed.

That distinction keeps the architecture documentation aligned with what is actually running.
