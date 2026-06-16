terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment to store state remotely (recommended before sharing with team)
  # backend "s3" {
  #   bucket = "my-tf-state-bucket"
  #   key    = "gpu-fabric-bench/dev/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  common_tags = {
    Project     = var.project
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

module "vpc" {
  source = "../../modules/vpc-hpc"

  name              = "${var.project}-dev"
  availability_zone = var.availability_zone
  ssh_cidr_blocks   = var.ssh_cidr_blocks
  tags              = local.common_tags
}

module "s3" {
  source = "../../modules/s3-results"

  name                  = var.results_bucket_name
  result_retention_days = 90
  tags                  = local.common_tags
}

module "cluster" {
  source = "../../modules/efa-cluster"

  name                   = "${var.project}-dev"
  instance_type          = var.instance_type
  node_count             = var.node_count
  efa_nic_count          = var.efa_nic_count
  subnet_id              = module.vpc.private_subnet_id
  security_group_ids     = [module.vpc.efa_security_group_id]
  key_name               = var.key_name
  s3_results_bucket_arn  = module.s3.bucket_arn
  tags                   = local.common_tags

  depends_on = [module.vpc, module.s3]
}

# Feed the cluster role ARN back into the S3 bucket policy
resource "aws_s3_bucket_policy" "cluster" {
  bucket = module.s3.bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ClusterReadWrite"
      Effect = "Allow"
      Principal = {
        AWS = [module.cluster.cluster_role_arn]
      }
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ]
      Resource = [
        module.s3.bucket_arn,
        "${module.s3.bucket_arn}/*"
      ]
    }]
  })
}
