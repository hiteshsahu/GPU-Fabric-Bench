## RDMA Primer — Verbs, Transports, and GPU Direct

> Covers the RDMA programming model end-to-end: memory registration, queue pairs, verbs API, transport types, and
> GPUDirect RDMA.  

---

## 🧠 What Is RDMA?

**RDMA (Remote Direct Memory Access)** lets one host read or write another host's memory directly — bypassing the remote
CPU and OS kernel entirely.

```
Without RDMA (TCP/IP):
  App → Kernel → NIC → Network → NIC → Kernel → App
        (copy)                         (copy)
        CPU involved both sides

With RDMA:
  App → NIC → Network → NIC → Remote Memory
        Hardware does all of it. CPU not involved.
```

**Why it matters for GPU clusters:**

- Eliminates CPU bottleneck in GPU-to-GPU data transfers
- Cuts latency from ~50–100 µs (TCP) to ~1–2 µs (IB RDMA)
- Saturates 400 Gb/s fabric without burning CPU cores
- Required for NCCL AllReduce at scale (gradient sync in LLM training)

---

## 🏗️ Core Concepts

### Memory Registration

Before RDMA can touch memory, the app must **register** it with the NIC:

```c
struct ibv_mr *mr = ibv_reg_mr(
    pd,           // protection domain
    buf,          // virtual address
    length,       // size in bytes
    IBV_ACCESS_LOCAL_WRITE |
    IBV_ACCESS_REMOTE_READ |
    IBV_ACCESS_REMOTE_WRITE
);
// mr->lkey  → local key (used in WRs you post)
// mr->rkey  → remote key (give to remote peer so they can RDMA into your buffer)
```

Registration pins pages in physical memory and gives the NIC a **key** to validate accesses. No key = NIC rejects the
operation. This is the primary security mechanism in RDMA.

---

### Queue Pair (QP) — The Core Abstraction

Every RDMA endpoint is a **Queue Pair**:

```
┌─────────────────────────────────────┐
│           Queue Pair (QP)           │
│                                     │
│  ┌───────────────┐  ┌─────────────┐ │
│  │  Send Queue   │  │ Recv Queue  │ │
│  │  (SQ)         │  │ (RQ)        │ │
│  │               │  │             │ │
│  │  Work Reqs →  │  │ ← Recv Bufs │ │
│  └───────────────┘  └─────────────┘ │
└──────────────────┬──────────────────┘
                   │ completions
          ┌────────▼─────────┐
          │ Completion Queue │
          │      (CQ)        │
          └──────────────────┘
```

| Object | What it is                                                        |
|--------|-------------------------------------------------------------------|
| **QP** | The logical endpoint; has a Send Queue + Recv Queue               |
| **SQ** | Where you post outgoing Work Requests (sends, RDMA writes, reads) |
| **RQ** | Where you post receive buffers for incoming sends                 |
| **CQ** | Where the NIC posts completion events when a WR finishes          |
| **WR** | Work Request — the unit of work you post to a queue               |
| **WC** | Work Completion — what the NIC writes to CQ when done             |

---

### Protection Domain (PD)

A **PD** is a namespace that scopes which QPs can access which memory registrations. A QP and an MR must belong to the
same PD to interact. Prevents cross-tenant memory access.

```c
struct ibv_pd *pd = ibv_alloc_pd(ctx);
```

---

## 🚛 Transport Types

| Transport | Full Name            | Reliable? | Connected?   | Use Case                            |
|-----------|----------------------|-----------|--------------|-------------------------------------|
| **RC**    | Reliable Connected   | ✅ Yes     | ✅ Yes (1:1)  | RDMA Read/Write, MPI, NCCL          |
| **UC**    | Unreliable Connected | ❌ No      | ✅ Yes (1:1)  | Rare; fire-and-forget bulk          |
| **UD**    | Unreliable Datagram  | ❌ No      | ❌ No (1:N)   | Subnet management, IPoIB, broadcast |
| **RD**    | Reliable Datagram    | ✅ Yes     | ❌ No (1:N)   | Not widely implemented              |
| **XRC**   | Extended RC          | ✅ Yes     | ✅ Shared SRQ | Scales RC to large job counts       |

### RC vs UD — The Scale Problem

RC requires one QP per process pair → **O(N²) connections** at scale:

```
1000 MPI ranks → 1000 × 999 / 2 = ~500,000 QPs
Each QP needs memory and NIC resources → hits hardware limits
```

AWS EFA's **SRD** transport solves this: connectionless like UD but reliable, so you get O(N) state instead of O(N²).

---

## ⚙️ RDMA Verbs Operations

### 1. RDMA Write

**Initiator pushes data into remote memory. Remote CPU is never involved.**

```c
struct ibv_send_wr wr = {
    .opcode     = IBV_WR_RDMA_WRITE,
    .wr.rdma = {
        .remote_addr = remote_vaddr,  // told to you out-of-band
        .rkey        = remote_rkey,   // told to you out-of-band
    },
    .sg_list = &sge,   // local source buffer
    .num_sge = 1,
};
ibv_post_send(qp, &wr, &bad_wr);
```

Best for: one-sided data push (gradient scatter in AllReduce).

### 2. RDMA Read

**Initiator pulls data from remote memory. Remote CPU not involved.**

```c
struct ibv_send_wr wr = {
    .opcode     = IBV_WR_RDMA_READ,
    .wr.rdma = {
        .remote_addr = remote_vaddr,
        .rkey        = remote_rkey,
    },
    .sg_list = &sge,   // local destination buffer
    .num_sge = 1,
};
ibv_post_send(qp, &wr, &bad_wr);
```

Higher latency than Write (round-trip to fetch data). Use Write where possible.

### 3. Send / Recv (Two-sided)

**Both sides involved. Receiver must post a Recv buffer before the Send arrives.**

```c
// Receiver posts a buffer first
struct ibv_recv_wr rwr = { .sg_list = &sge, .num_sge = 1 };
ibv_post_recv(qp, &rwr, &bad_rwr);

// Sender posts a send
struct ibv_send_wr wr = { .opcode = IBV_WR_SEND, .sg_list = &sge, .num_sge = 1 };
ibv_post_send(qp, &wr, &bad_wr);
```

Use for: control messages, connection setup, small metadata exchange.

### 4. Atomic Operations

**Compare-and-Swap or Fetch-and-Add directly in remote memory.**

```c
wr.opcode = IBV_WR_ATOMIC_CMP_AND_SWP;
wr.wr.atomic.compare_add = expected;
wr.wr.atomic.swap        = new_value;
```

Use for: distributed lock-free counters, barrier synchronization primitives.

---

## 🔄 Connection Setup Flow (RC)

```
Node A                              Node B
  │                                   │
  │── ibv_open_device()               │── ibv_open_device()
  │── ibv_alloc_pd()                  │── ibv_alloc_pd()
  │── ibv_create_cq()                 │── ibv_create_cq()
  │── ibv_create_qp()                 │── ibv_create_qp()
  │── ibv_modify_qp() → INIT          │── ibv_modify_qp() → INIT
  │                                   │
  │←──── exchange QPN + LID/GID ─────►│  (out-of-band: TCP socket or MPI)
  │                                   │
  │── ibv_modify_qp() → RTR           │── ibv_modify_qp() → RTR
  │── ibv_modify_qp() → RTS           │── ibv_modify_qp() → RTS
  │                                   │
  │◄═══════ RDMA now possible ════════►│
```

| QP State  | Meaning                                              |
|-----------|------------------------------------------------------|
| **RESET** | Just created, can't do anything                      |
| **INIT**  | Resources allocated, not yet connected               |
| **RTR**   | Ready To Receive — can post Recv WRs                 |
| **RTS**   | Ready To Send — fully operational, can post Send WRs |

---

## 🖥️ GPUDirect RDMA

**GPUDirect RDMA** allows the NIC to DMA directly into/from GPU memory over PCIe — no CPU, no copies through system RAM.

```
Without GPUDirect:
  GPU HBM → (PCIe) → System RAM → (PCIe) → NIC → Network
  Two PCIe crossings, CPU/driver involved

With GPUDirect RDMA:
  GPU HBM → (PCIe) → NIC → Network
  One PCIe crossing, CPU not involved
```

### Registration with CUDA

```c
// Pin GPU buffer into RDMA address space
cudaMalloc(&gpu_buf, size);
ibv_reg_mr(pd, gpu_buf, size,
    IBV_ACCESS_LOCAL_WRITE |
    IBV_ACCESS_REMOTE_WRITE |
    IBV_ACCESS_REMOTE_READ);
// Same ibv_reg_mr call — CUDA driver intercepts and pins GPU pages
```

### Requirements

| Requirement | Detail                                                                     |
|-------------|----------------------------------------------------------------------------|
| NIC         | Mellanox ConnectX-4 or newer (or EFA on p4d)                               |
| GPU         | NVIDIA Kepler or newer                                                     |
| Driver      | MLNX_OFED + `nv_peer_mem` kernel module (or GDRCopy for GPU reads)         |
| PCIe        | GPU and NIC must share the same PCIe root complex (same NUMA node ideally) |
| Kernel flag | `NCCL_P2P_DISABLE=0` (default)                                             |

### NUMA Topology Matters

```bash
# Check GPU-NIC PCIe affinity — want same CPU socket
nvidia-smi topo -m

# Output shows P2P access between GPU0 and mlx5_0:
# GPU0  mlx5_0  PIX   ← PCIe switch (fast, ~200 GB/s)
# GPU0  mlx5_2  SYS   ← cross-socket (slow, ~40 GB/s)
```

---

## 📋 Verbs API Quick Reference

```c
// Device / context
ibv_get_device_list()       // enumerate RDMA devices
ibv_open_device(dev)        // open device, get ctx

// Resource creation
ibv_alloc_pd(ctx)           // protection domain
ibv_create_cq(ctx, cqe, …) // completion queue
ibv_create_qp(pd, &attr)   // queue pair
ibv_reg_mr(pd, addr, len, flags) // register memory

// QP state machine
ibv_modify_qp(qp, &attr, mask)  // RESET → INIT → RTR → RTS

// Work posting
ibv_post_send(qp, &wr, &bad)    // post send/write/read WR
ibv_post_recv(qp, &wr, &bad)    // post recv buffer

// Completions
ibv_poll_cq(cq, num, &wc)       // poll for completions (non-blocking)
ibv_req_notify_cq(cq, 0)        // arm CQ for event notification
ibv_get_cq_event(channel, …)    // block until CQ event

// Teardown
ibv_dereg_mr(mr)
ibv_destroy_qp(qp)
ibv_destroy_cq(cq)
ibv_dealloc_pd(pd)
ibv_close_device(ctx)
```

---

## 🔧 Debugging Commands

```bash
# List RDMA devices and their state
ibstat
ibv_devinfo

# Check port details (speed, state, LID)
ibstat mlx5_0 1

# Bandwidth test — RDMA Write (RC transport)
# on receiver:
ib_write_bw -d mlx5_0
# on sender:
ib_write_bw -d mlx5_0 <receiver-hostname>

# Latency test — RDMA Send (RC transport)
ib_send_lat -d mlx5_0                 # receiver
ib_send_lat -d mlx5_0 <receiver>      # sender

# RDMA Read bandwidth
ib_read_bw -d mlx5_0
ib_read_bw -d mlx5_0 <receiver>

# Check QP counters (retransmits, errors)
perfquery -x 0 1   # port 1 extended counters
# or via sysfs:
cat /sys/class/infiniband/mlx5_0/ports/1/counters/VL15_dropped

# GPUDirect: verify nv_peer_mem is loaded
lsmod | grep nv_peer_mem
dmesg | grep "nv_peer_mem"

# Check PCIe topology for GPU-NIC affinity
nvidia-smi topo -m

# GDRCopy version (CPU-initiated GPU reads via BAR mapping)
gdrcopy_sanity
```

---

## 🗺️ How This Maps to AWS EFA

| RDMA Concept        | InfiniBand / libibverbs                 | AWS EFA / libfabric                                      |
|---------------------|-----------------------------------------|----------------------------------------------------------|
| Verbs API           | `libibverbs` (`ibv_*`)                  | `libfabric` (`fi_*`) with EFA provider                   |
| Transport           | RC / UD / XRC                           | SRD (Scalable Reliable Datagram)                         |
| Memory registration | `ibv_reg_mr`                            | `fi_mr_reg`                                              |
| Queue Pair          | QP (SQ + RQ)                            | Endpoint (TX + RX)                                       |
| Completion Queue    | CQ (`ibv_poll_cq`)                      | Completion Queue (`fi_cq_read`)                          |
| RDMA Write          | `IBV_WR_RDMA_WRITE`                     | `fi_write` (device RDMA with `FI_EFA_USE_DEVICE_RDMA=1`) |
| Connection setup    | QP state machine (RTR/RTS)              | No connection needed (datagram)                          |
| GPUDirect RDMA      | `nv_peer_mem` + `ibv_reg_mr` on GPU buf | `FI_EFA_USE_DEVICE_RDMA=1` on p4d instances              |
| Subnet manager      | OpenSM (`opensm`)                       | AWS-managed (not accessible)                             |

---

## 💡 Common Questions

| Question                         | Answer                                                                                                                    |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Why register memory before RDMA? | Pins physical pages, gives NIC a key to validate remote access                                                            |
| RC vs UD?                        | RC: reliable + connected (1:1 QP); UD: unreliable + connectionless (1:N, no per-peer state)                               |
| Why RDMA Write over RDMA Read?   | Write is one-shot push (sender initiates, no remote round-trip); Read needs the remote NIC to fetch back = higher latency |
| What is a completion event?      | NIC writes a Work Completion (WC) to the CQ when a posted WR finishes — app polls CQ to know it's done                    |
| GPUDirect RDMA bottleneck?       | PCIe bandwidth (~64 GB/s on PCIe 4.0 x16) — NVSwitch fixes intra-node, but inter-node is still PCIe-bound                 |
| O(N²) problem?                   | RC needs a QP per process pair; 1000 ranks = 500K QPs. EFA SRD / IB XRC solves this                                       |
| What is lkey vs rkey?            | lkey: your local access key for your own memory; rkey: the key you give a remote peer so they can RDMA into your buffer   |
