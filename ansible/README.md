## Ansible EFA Cluster Provisioning

Idempotent provisioning of EFA cluster nodes. Mirrors what
`terraform/modules/efa-cluster/templates/user_data.sh.tpl` does at boot,
but structured for re-runs, partial installs, and day-2 operations.

### Quick start

```bash
# 1. Copy and fill in cluster IPs (from `terraform output private_ips`)
cp inventory/hosts.ini.example inventory/hosts.ini
nano inventory/hosts.ini

# 2. Run full provisioning
ansible-playbook -i inventory/hosts.ini site.yml

# 3. Verify EFA on all nodes
ansible cluster -i inventory/hosts.ini -m command \
  -a "/opt/amazon/efa/bin/fi_info -p efa"
```

### Selective runs with tags

```bash
# EFA driver only
ansible-playbook -i inventory/hosts.ini site.yml --tags efa

# MPI stack + OSU benchmarks, skip NCCL
ansible-playbook -i inventory/hosts.ini site.yml --tags mpi

# NCCL layer only (p4d nodes)
ansible-playbook -i inventory/hosts.ini site.yml --tags nccl

# Refresh MPI hostfile after node replacement
ansible-playbook -i inventory/hosts.ini site.yml --tags hostfile
```

### Overriding defaults

Each role has a `defaults/main.yml`. Override at play time:

```bash
ansible-playbook -i inventory/hosts.ini site.yml \
  -e openmpi_version=4.1.7 \
  -e "nccl_env_vars={'NCCL_ALGO':'Tree','NCCL_PROTO':'LL'}"
```

### Role defaults

### efa-setup

| Variable | Default |
|----------|---------|
| `efa_installer_url` | `https://efa-installer.amazonaws.com/aws-efa-installer-latest.tar.gz` |
| `efa_install_dir` | `/opt/amazon/efa` |

### openmpi

| Variable | Default |
|----------|---------|
| `openmpi_version` | `4.1.6` |
| `openmpi_prefix` | `/opt/openmpi` |

### osu-benchmarks

| Variable | Default |
|----------|---------|
| `osu_version` | `7.3` |
| `osu_prefix` | `/opt/osu` |

### nccl-install

| Variable | Default |
|----------|---------|
| `nccl_home` | `/usr/local/nccl` |
| `cuda_home` | auto-detected from `nvcc` |
| `nccl_env_vars` | see `defaults/main.yml` |

---
### Relationship to Terraform user_data

`user_data.sh.tpl` runs once at first boot and has no idempotency
guarantees. These roles are preferred for:

- Re-provisioning after an instance is stopped and restarted
- Updating a single component (e.g., newer OSU version) without full
  node replacement
- Debugging — Ansible's `--check` and `--diff` flags show exactly what
  would change without applying it

See [terraform/modules/efa-cluster/README.md](../terraform/modules/efa-cluster/README.md)
for the Terraform side and [docs/rdma-primer.md](../docs/rdma-primer.md) for
EFA/RDMA background.
