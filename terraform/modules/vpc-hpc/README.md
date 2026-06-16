# vpc-hpc — Network Layer

HPC-optimized VPC for EFA cluster: single-AZ private subnet, NAT gateway, and EFA security group.

## Resources

| Resource | Purpose |
|----------|---------|
| `aws_vpc` | Single VPC; DNS hostnames enabled for MPI host resolution |
| `aws_subnet` (private) | Single-AZ; all cluster nodes live here — placement groups are AZ-scoped |
| `aws_subnet` (public) | NAT gateway only; nodes have no public IPs |
| `aws_nat_gateway` | Outbound internet for package installs from private nodes |
| `aws_security_group` `efa` | Self-referential all-traffic rule (required by EFA for RDMA) |

## Why the self-referential SG rule?

EFA validates that both endpoints of an RDMA connection belong to the same security group. The all-traffic intra-SG rule is mandatory — narrowing it breaks RDMA.

## Inputs

| Variable | Default | Description |
|----------|---------|-------------|
| `name` | — | Resource name prefix |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR block |
| `private_subnet_cidr` | `10.0.1.0/24` | Cluster nodes subnet |
| `public_subnet_cidr` | `10.0.0.0/24` | NAT gateway subnet |
| `availability_zone` | — | Single AZ for placement group locality |
| `ssh_cidr_blocks` | `["0.0.0.0/0"]` | CIDRs allowed to SSH |

## Outputs

| Output | Description |
|--------|-------------|
| `vpc_id` | VPC ID |
| `private_subnet_id` | Subnet ID for cluster nodes |
| `public_subnet_id` | Subnet ID for NAT GW |
| `efa_security_group_id` | SG ID to pass to `efa-cluster` |

## Further reading

- [IB vs EFA Deep Dive](ib-vs-efa.md)
- [ADR-1: Single-AZ Placement](../../../docs/adr/1-single-az-placement.md)
