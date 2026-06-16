# s3-results — Storage Layer

Versioned S3 bucket for benchmark result storage with automatic expiry and cluster-scoped access policy.

## Resources

| Resource | Purpose |
|----------|---------|
| `aws_s3_bucket` | Stores benchmark CSVs, logs, bandwidth curves |
| `aws_s3_bucket_versioning` | Keeps history of result files across benchmark runs |
| `aws_s3_bucket_lifecycle_configuration` | Expires objects after 90 days (configurable) |
| `aws_s3_bucket_public_access_block` | All four public-access blocks enabled |
| `aws_s3_bucket_policy` | Grants cluster IAM role read/write; no other access |

## Inputs

| Variable | Default | Description |
|----------|---------|-------------|
| `name` | — | S3 bucket name (must be globally unique) |
| `cluster_role_arns` | `[]` | IAM role ARNs allowed to read/write results |
| `result_retention_days` | `90` | Days before objects expire |

## Outputs

| Output | Description |
|--------|-------------|
| `bucket_id` | Bucket name |
| `bucket_arn` | Bucket ARN (pass to `efa-cluster` for instance policy) |
