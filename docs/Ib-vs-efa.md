## InfiniBand vs AWS EFA -- Deep Dive

> This doc maps physical InfiniBand concepts to AWS EFA equivalents.  
> Designed as interview prep for NVIDIA GPU infrastructure roles.

### 🚛 Transport Layer Comparison

### 1. Transport Protocol

- IB uses **RC (Reliable Connected)** — like TCP for RDMA; connection per pair of processes
- EFA uses **SRD (Scalable Reliable Datagram)** — connectionless, scales better for large job counts
- SRD eliminates the O(N²) connection problem that plagues RC at scale

### 2. Latency Gap

- Physical IB NDR: ~1 µs MPI latency
- EFA: ~15–25 µs MPI latency
- Gap matters for latency-sensitive ops (small AllReduce in tight training loops)
- For large message bandwidth (gradient sync in LLM training), gap is much smaller

### 3. Topology Control

- IB: You control switch fabric — can tune routing, adaptive routing, ECMP
- EFA: AWS manages fabric — you get cluster placement groups as the only knob
- Implication: can't diagnose "hot links" on EFA the way you can with `ibnetdiscover`

| Concept             | Physical InfiniBand 🪢                | AWS EFA  📡                                          |
|---------------------|---------------------------------------|------------------------------------------------------| 
| **Transport**       | `RC` (Reliable Connected), UC, UD, RD | `SRD` (Scalable Reliable Datagram) — AWS proprietary |
| **Verbs API**       | libibverbs (ibv_post_send etc.)       | libfabric with EFA provider                          |
| **Kernel bypass**   | Yes — RDMA direct to NIC              | Yes — bypasses OS network stack                      |
| **Zero-copy**       | Yes                                   | Yes                                                  |
| **RDMA Write/Read** | Full support                          | Supported (device RDMA)                              |
| **Max bandwidth**   | NDR: 400 Gb/s per port                | Up to 100 Gb/s (c5n), 400 Gb/s (p4d cluster)         |
| **Latency**         | `~1 µs` MPI latency                   | `~15–25` µs MPI latency                              |
| **Switch fabric**   | Fat-tree, Dragonfly+                  | AWS-managed (opaque)                                 |

### 📦 Hardware Layer Comparison

| Component      | InfiniBand 🪢                  | EFA 📡                                         |
|----------------|--------------------------------|------------------------------------------------|
| NIC            | Mellanox/NVIDIA ConnectX (HCA) | AWS EFA NIC (custom silicon)                   |
| Driver         | MLNX_OFED (OpenFabrics)        | aws-efa-installer (libfabric)                  |
| Check device   | `ibstat`, `ibv_devinfo`        | `fi_info -p efa`                               |
| Multiple ports | HCA has 1–2 ports              | Up to 4x EFA NICs per p4d instance             |
| GPU Direct     | GPUDirect RDMA via PCIe        | Supported on p4d with FI_EFA_USE_DEVICE_RDMA=1 |

### 🔗 NCCL Configuration

| Parameter | InfiniBand 🪢                             | EFA 📡                                      |
|-----------|-------------------------------------------|---------------------------------------------|
| Transport | `NCCL_IB_DISABLE=0`, `NCCL_IB_HCA=mlx5_0` | `NCCL_IB_HCA=efa`, `NCCL_SOCKET_IFNAME=efa` |
| Plugin    | nccl-rdma-sharp-plugin                    | aws-ofi-nccl plugin                         |
| GPUDirect | Automatic if GPUDirect RDMA present       | Requires `FI_EFA_USE_DEVICE_RDMA=1`         |

### Debugging Tools

| Task               | InfiniBand 🪢      | EFA 📡                         |
|--------------------|--------------------|--------------------------------|
| Check link status  | `ibstat`           | `fi_info -p efa`               |
| Bandwidth test     | `ib_write_bw`      | `osu_bw` over MPI              |
| Latency test       | `ib_send_lat`      | `osu_latency` over MPI         |
| Topology discovery | `ibnetdiscover`    | Not available (AWS-managed)    |
| NCCL debug         | `NCCL_DEBUG=INFO`  | Same                           |
| Packet captures    | `tcpdump` on IPoIB | Not applicable (kernel bypass) |

### NVIDIA SuperPOD vs AWS EFA Cluster

| Aspect             | NVIDIA SuperPOD (NDR IB)            | AWS p4d Cluster (EFA)               |
|--------------------|-------------------------------------|-------------------------------------|
| GPU-GPU bandwidth  | 900 GB/s NVSwitch + 400 Gb/s IB     | 400 Gb/s EFA aggregate              |
| Topology           | NVSwitch (intra-node) + fat-tree IB | NVLink (intra-node) + EFA           |
| NVLink generations | NVLink 4.0 (H100)                   | NVLink 3.0 (A100)                   |
| Scale              | Up to 32 nodes (DGX SuperPOD)       | Up to hundreds via placement groups |
| Routing control    | Full (OpenSM)                       | None (AWS-managed)                  |

---

## Useful Commands Cheatsheet

```bash
# Verify EFA device
fi_info -p efa

# Check EFA interface details
fi_info -p efa -v | grep -E 'fabric|domain|tx_size|rx_size'

# Test EFA bandwidth (2 nodes, run on head node)
mpirun --hostfile ~/hostfile --np 2 --map-by node osu_bw

# Test MPI latency over EFA
mpirun --hostfile ~/hostfile --np 2 --map-by node osu_latency

# Run NCCL AllReduce with debug output
NCCL_DEBUG=INFO mpirun --hostfile ~/hostfile --np 16 all_reduce_perf \
  --minbytes 1G --maxbytes 1G --iters 10

# Check EFA driver version
cat /opt/amazon/efa/RELEASES.md | head -5
```