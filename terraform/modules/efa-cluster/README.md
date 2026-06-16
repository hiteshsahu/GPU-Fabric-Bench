# efa-cluster — Compute Layer

Provisions GPU/CPU nodes in a cluster placement group with EFA NICs for RDMA benchmarking.


```text
    
    ┌─────────────────────────────────────────────────────┐
    │              AWS Cluster Placement Group            │
    │                                                     │
    │  ┌──────────────┐  EFA   ┌──────────────┐           │
    │  │ p4d.24xlarge │◄──────►│ p4d.24xlarge │           │
    │  │  8x A100 GPU │        │  8x A100 GPU │           │
    │  │  4x EFA NICs │        │  4x EFA NICs │           │
    │  └──────┬───────┘        └──────┬───────┘           │
    │         │                       │                   │
    │  ┌──────▼───────────────────────▼────────┐          │
    │  │        HPC-optimized VPC              │          │
    │  │  Jumbo frames (9001 MTU)              │          │
    │  │  Enhanced networking (SR-IOV)         │          │
    │  │  EFA security group (all intra-SG)    │          │
    │  └───────────────────────────────────────┘          │
    └─────────────────────────────────────────────────────┘
                            │
                  ┌─────────▼──────────┐
                  │  S3 Results Bucket │
                  │  benchmark outputs │
                  │  bandwidth curves  │
                  └────────────────────┘


```

## Resources

| Resource                           | Purpose                                                            |
|------------------------------------|--------------------------------------------------------------------|
| `aws_placement_group` (`cluster`)  | Packs nodes onto the same physical spine for lowest fabric latency |
| `aws_network_interface` (primary)  | `eth0` — regular ENI for SSH, SSM, and MPI control messages        |
| `aws_network_interface` (EFA)      | `eth1..N` — `interface_type = "efa"`, enables kernel bypass + RDMA |
| `aws_network_interface_attachment` | Attaches EFA NICs after instance creation at `device_index` 1..N   |
| `aws_instance`                     | Node itself; primary NIC at `device_index = 0`                     |
| `aws_iam_role`                     | Instance profile with SSM access + S3 write for result upload      |
w
## NIC layout per node

```
eth0  →  aws_network_interface (regular ENI)   — SSH / control plane
eth1  →  aws_network_interface (EFA)           — RDMA data plane
eth2  →  aws_network_interface (EFA)           — (p4d only)
eth3  →  aws_network_interface (EFA)           — (p4d only)
eth4  →  aws_network_interface (EFA)           — (p4d only)
```

EFA NICs cannot be the primary interface in Terraform (primary must be a regular ENI), so they are created separately
and attached. NCCL is pointed at the EFA NICs via `NCCL_IB_HCA=efa`.

## AMI selection

| Instance family           | AMI                                                       |
|---------------------------|-----------------------------------------------------------|
| `p4d.*`, `p3.*`, `p5.*`   | AWS Deep Learning AMI (PyTorch, CUDA, NCCL pre-installed) |
| `c5n.*`, `c6gn.*`, others | Amazon Linux 2 (EFA installed via user data)              |

Override with `ami_id` variable if needed.

## User data (`templates/user_data.sh.tpl`)

Installs on first boot:

- AWS EFA driver (`efa_installer.sh`)
- OpenMPI (if not present from DLAMI)
- OSU micro-benchmarks (`osu_latency`, `osu_bw`)
- `aws-ofi-nccl` plugin (GPU only) — bridges NCCL → libfabric → EFA
- `nccl-tests` (`all_reduce_perf`, `all_gather_perf`) (GPU only)
- Default NCCL env vars in `/etc/profile.d/nccl-efa.sh`

## Inputs

| Variable                | Default        | Description                        |
|-------------------------|----------------|------------------------------------|
| `name`                  | —              | Resource name prefix               |
| `instance_type`         | `c5n.18xlarge` | EC2 instance type                  |
| `node_count`            | `2`            | Number of cluster nodes            |
| `efa_nic_count`         | `1`            | EFA NICs per node (4 for p4d)      |
| `subnet_id`             | —              | Private subnet from `vpc-hpc`      |
| `security_group_ids`    | —              | EFA SG from `vpc-hpc`              |
| `key_name`              | —              | EC2 key pair for SSH               |
| `ami_id`                | `""`           | Override AMI (empty = auto-select) |
| `s3_results_bucket_arn` | —              | ARN of results bucket              |

## Outputs

| Output             | Description                            |
|--------------------|----------------------------------------|
| `instance_ids`     | EC2 instance IDs                       |
| `private_ips`      | Primary NIC IPs                        |
| `cluster_role_arn` | IAM role ARN (used to grant S3 access) |
| `mpi_hostfile`     | Ready-to-paste MPI hostfile content    |
| `ssh_commands`     | SSM session commands for each node     |

## Further reading

- [RDMA Primer](rdma-primer.md)
