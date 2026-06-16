output "vpc_id" {
  value = module.vpc.vpc_id
}

output "instance_ids" {
  value = module.cluster.instance_ids
}

output "private_ips" {
  value = module.cluster.private_ips
}

output "results_bucket" {
  value = module.s3.bucket_id
}

output "mpi_hostfile" {
  description = "Paste into ~/hostfile on the head node"
  value       = module.cluster.mpi_hostfile
}

output "ssm_commands" {
  description = "Connect to nodes without public IPs via SSM"
  value       = module.cluster.ssh_commands
}
