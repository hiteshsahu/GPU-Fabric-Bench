variable "name" {
  type        = string
  description = "Resource name prefix"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "VPC CIDR block"
}

variable "private_subnet_cidr" {
  type        = string
  default     = "10.0.1.0/24"
  description = "Private subnet for cluster nodes"
}

variable "public_subnet_cidr" {
  type        = string
  default     = "10.0.0.0/24"
  description = "Public subnet for NAT gateway only"
}

variable "availability_zone" {
  type        = string
  description = "Single AZ for placement group locality"
}

variable "ssh_cidr_blocks" {
  type        = list(string)
  default     = ["0.0.0.0/0"]
  description = "CIDR blocks allowed to SSH to cluster nodes"
}

variable "tags" {
  type    = map(string)
  default = {}
}
