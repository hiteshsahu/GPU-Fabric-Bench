## GPU Fabric Bench Infrastructure

Provisions a two-node (or N-node) EFA cluster on AWS for NCCL and MPI benchmarking.

---

## Architecture

```
                        ┌─────────────────────────────────────────────────┐
                        │              AWS Region (us-east-1)             │
                        │                                                 │
                        │  ┌──────────────────────────────────────────┐   │
                        │  │         VPC  10.0.0.0/16                │   │
                        │  │                                          │   │
                        │  │  ┌─────────────┐  ┌─────────────────┐   │   │
                        │  │  │ Public /24  │  │  Private /24    │   │   │
                        │  │  │  NAT GW     │  │  (single AZ)    │   │   │
                        │  │  └──────┬──────┘  └────────┬────────┘   │   │
                        │  │         │                   │            │   │
                        │  │         └───── routes ──────┘            │   │
                        │  │                                          │   │
                        │  │  ┌─────────────────────────────────┐     │   │
                        │  │  │   Cluster Placement Group       │     │   │
                        │  │  │                                 │     │   │
                        │  │  │  ┌─────────────┐ ┌───────────┐ │     │   │
                        │  │  │  │ Node 0      │ │  Node 1   │ │     │   │
                        │  │  │  │ eth0 (mgmt) │ │ eth0      │ │     │   │
                        │  │  │  │ efa0..3     │ │ efa0..3   │ │     │   │
                        │  │  │  └──────┬──────┘ └─────┬─────┘ │     │   │
                        │  │  │         │    EFA fabric │       │     │   │
                        │  │  │         └───────────────┘       │     │   │
                        │  │  └─────────────────────────────────┘     │   │
                        │  └──────────────────────────────────────────┘   │
                        │                      │                           │
                        │              ┌───────▼────────┐                 │
                        │              │  S3 Results    │                 │
                        │              │  Bucket        │                 │
                        │              └────────────────┘                 │
                        └─────────────────────────────────────────────────┘
```

See [ADR-1: Deploy all cluster nodes in a single Availability Zone](../docs/adr/1-single-az-placement.md).


---

## Module Structure

```
terraform/
├── modules/
│   ├── vpc-hpc/          # Network layer
│   ├── efa-cluster/      # Compute layer
│   └── s3-results/       # Storage layer
└── environments/
    └── dev/              # Entry point — wires all three modules together
```

### 1. [`vpc-hpc`](modules/vpc-hpc/README.md) — Network Layer

VPC, subnets, NAT gateway, and EFA security group.

### 2. [`efa-cluster`](modules/efa-cluster/README.md) — Compute Layer

Placement group, EFA NICs, EC2 instances, IAM role, and bootstrap user data.

### 3. [`s3-results`](modules/s3-results/README.md) — Storage Layer

Versioned S3 bucket with lifecycle expiry and cluster-scoped access policy.

---

## Quick Start

```bash
cd terraform/environments/dev

# 1. Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Set: key_name, results_bucket_name, instance_type, ssh_cidr_blocks

# 2. Init and apply
terraform init
terraform plan
terraform apply

# 3. Grab the MPI hostfile from outputs
terraform output mpi_hostfile

# 4. Connect to head node (no public IPs — SSM only)
terraform output ssm_commands   # copy the first command
aws ssm start-session --target i-xxxx --region us-east-1

# 5. Run a benchmark from the head node
echo "$(terraform output -raw mpi_hostfile)" > ~/hostfile
mpirun --hostfile ~/hostfile --np 2 --map-by node osu_latency
```

---

## Instance Selection

| Goal                          | `instance_type` | `efa_nic_count` | Cost          |
|-------------------------------|-----------------|-----------------|---------------|
| EFA + MPI + OSU only (no GPU) | `c5n.18xlarge`  | `1`             | ~$3.88/hr × 2 |
| Full NCCL GPU benchmark       | `p4d.24xlarge`  | `4`             | ~$32/hr × 2   |

Check AZ capacity before applying — p4d availability varies by AZ:

```bash
aws ec2 describe-instance-type-offerings \
  --location-type availability-zone \
  --filters Name=instance-type,Values=p4d.24xlarge \
  --region us-east-1 \
  --query 'InstanceTypeOfferings[].Location'
```

---

## Teardown

```bash
# Terminate everything — EBS volumes and S3 objects are deleted automatically
terraform destroy
```

> The S3 bucket is created with `force_destroy = true` so `terraform destroy` empties and removes it. Remove that flag
> if you want to preserve results across Terraform runs.

---

## Remote State (optional)

Uncomment the `backend "s3"` block in [environments/dev/main.tf](environments/dev/main.tf) and create the state bucket
first:

```bash
aws s3 mb s3://my-tf-state-bucket --region us-east-1
aws s3api put-bucket-versioning \
  --bucket my-tf-state-bucket \
  --versioning-configuration Status=Enabled
```
