variable "name" {
  type        = string
  description = "S3 bucket name (must be globally unique)"
}

variable "cluster_role_arns" {
  type        = list(string)
  default     = []
  description = "IAM role ARNs that may read/write benchmark results"
}

variable "result_retention_days" {
  type        = number
  default     = 90
  description = "Days to retain benchmark result objects before expiry"
}

variable "tags" {
  type    = map(string)
  default = {}
}
