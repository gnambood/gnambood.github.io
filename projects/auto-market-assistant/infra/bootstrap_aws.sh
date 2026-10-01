#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-ca-central-1}"
PROJECT="auto-market-assistant"
REPO="gnambood/gnambood.github.io"
REPO_OWNER_ID="230923225"
REPO_ID="1378971855"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${ARTIFACT_BUCKET:-${PROJECT}-${ACCOUNT_ID}-${REGION}}"
ECR_REPO="${ECR_REPOSITORY:-${PROJECT}}"
ROLE_NAME="${GITHUB_ROLE_NAME:-AutoMarketGitHubDeployRole}"

echo "AWS account: ${ACCOUNT_ID}"
echo "Region:      ${REGION}"
echo "Bucket:      ${BUCKET}"
echo "ECR repo:    ${ECR_REPO}"

if ! aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket       --bucket "${BUCKET}"       --region "${REGION}"       --create-bucket-configuration LocationConstraint="${REGION}"
  fi
fi

aws s3api put-public-access-block   --bucket "${BUCKET}"   --public-access-block-configuration   BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-versioning   --bucket "${BUCKET}"   --versioning-configuration Status=Enabled

aws ecr describe-repositories   --repository-names "${ECR_REPO}"   --region "${REGION}" >/dev/null 2>&1 || aws ecr create-repository   --repository-name "${ECR_REPO}"   --region "${REGION}"   --image-scanning-configuration scanOnPush=true >/dev/null

OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

if ! aws iam get-open-id-connect-provider   --open-id-connect-provider-arn "${OIDC_ARN}" >/dev/null 2>&1; then
  aws iam create-open-id-connect-provider     --url https://token.actions.githubusercontent.com     --client-id-list sts.amazonaws.com     --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
fi

cat > /tmp/auto-market-trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "${OIDC_ARN}"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:${REPO}:ref:refs/heads/main",
          "repo:gnambood@${REPO_OWNER_ID}/gnambood.github.io@${REPO_ID}:ref:refs/heads/main"
        ]
      }
    }
  }]
}
EOF

if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  aws iam update-assume-role-policy     --role-name "${ROLE_NAME}"     --policy-document file:///tmp/auto-market-trust.json
else
  aws iam create-role     --role-name "${ROLE_NAME}"     --assume-role-policy-document file:///tmp/auto-market-trust.json >/dev/null
fi

cat > /tmp/auto-market-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart"
      ],
      "Resource": "arn:aws:ecr:${REGION}:${ACCOUNT_ID}:repository/${ECR_REPO}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateExpressGatewayService",
        "ecs:DescribeExpressGatewayService",
        "ecs:RegisterTaskDefinition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
        "arn:aws:iam::${ACCOUNT_ID}:role/AutoMarketTaskRole",
        "arn:aws:iam::${ACCOUNT_ID}:role/ecsInfrastructureRoleForExpressServices"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": [
            "ecs-tasks.amazonaws.com",
            "ecs.amazonaws.com"
          ]
        }
      }
    }
  ]
}
EOF

aws iam put-role-policy   --role-name "${ROLE_NAME}"   --policy-name AutoMarketGitHubDeploy   --policy-document file:///tmp/auto-market-policy.json

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"

echo
echo "AWS bootstrap complete."
echo
echo "Save these values:"
echo "AWS_REGION=${REGION}"
echo "ARTIFACT_BUCKET=${BUCKET}"
echo "ECR_REPOSITORY=${ECR_REPO}"
echo "ECR_URI=${ECR_URI}"
echo "AWS_ROLE_ARN=${ROLE_ARN}"
echo
echo "Next: upload the project artifacts, build/push the first container image, then create the ECS Express Mode service."
