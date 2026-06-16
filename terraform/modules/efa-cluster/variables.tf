variable "name" {
  type        = string
  description = "Resource name prefix"
}

variable "instance_type" {
  type        = string
  default     = "c5n.18xlarge"
  description = "EC2 instance type; use c5n.18xlarge for CPU-only EFA testing or p4d.24xlarge for GPU benchmarks"
}

variable "node_count" {
  type        = number
  default     = 2
  description = "Number of cluster nodes"
}

variable "efa_nic_count" {
  type        = number
  default     = 1
  description = "Number of EFA NICs per node; p4d.24xlarge supports 4, c5n.18xlarge supports 1"
}

variable "subnet_id" {
  type        = string
  description = "Private subnet ID for cluster nodes"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs (must include the EFA intra-SG rule)"
}

variable "key_name" {
  type        = string
  description = "EC2 key pair name for SSH access"
}

variable "ami_id" {
  type        = string
  default     = ""
  description = "AMI ID override; leave empty to auto-select DLAMI for GPU or AL2 for CPU instances"
}

variable "s3_results_bucket_arn" {
  type        = string
  description = "S3 bucket ARN for benchmark result uploads"
}

variable "tags" {
  type    = map(string)
  default = {}
}
