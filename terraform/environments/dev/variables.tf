variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "availability_zone" {
  type        = string
  default     = "us-east-1a"
  description = "Single AZ for all cluster resources; placement groups are AZ-scoped"
}

variable "project" {
  type    = string
  default = "gpu-fabric-bench"
}

variable "instance_type" {
  type        = string
  default     = "c5n.18xlarge"
  description = "c5n.18xlarge for EFA+MPI testing (~$3.88/hr); p4d.24xlarge for full NCCL GPU benchmarks (~$32/hr)"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "efa_nic_count" {
  type        = number
  default     = 1
  description = "Set to 4 when using p4d.24xlarge"
}

variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name"
}

variable "ssh_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "results_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for benchmark results"
}
