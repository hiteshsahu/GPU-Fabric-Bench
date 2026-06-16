output "instance_ids" {
  value = aws_instance.node[*].id
}

output "private_ips" {
  value = aws_network_interface.primary[*].private_ip
}

output "cluster_role_arn" {
  value = aws_iam_role.cluster.arn
}

# MPI hostfile content — paste into ~/hostfile on the head node
output "mpi_hostfile" {
  value = join("\n", [
    for i, ip in aws_network_interface.primary[*].private_ip :
    "${ip} slots=${local.is_gpu_instance ? 8 : 72}"
  ])
}

output "ssh_commands" {
  value = [
    for i, id in aws_instance.node[*].id :
    "aws ssm start-session --target ${id} --region ${data.aws_region.current.name}"
  ]
}
