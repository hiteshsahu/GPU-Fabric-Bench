## ADR-1: Deploy all cluster nodes in a single Availability Zone

**Status:** Accepted  
**Date:** 2026-06-16  
**Context:** Terraform EFA cluster module (`terraform/modules/efa-cluster`)

---

## ℹ️ Context

The benchmark cluster uses an AWS cluster placement group to minimize fabric latency between nodes.

EFA (Elastic Fabric Adapter) RDMA traffic must travel over the intra-cluster fabric to achieve the target bandwidth (~400 Gb/s aggregate) and latency (~15–25 µs MPI).

## 📜 Decision

> All cluster nodes are deployed into a **single Availability Zone** subnet. 

The VPC module creates one private subnet pinned to a specific AZ, and all instances in the efa-cluster module use that subnet.

## 💡 Reasons

### 1. **Cluster placement groups are limited to a single AZ.** 
> AWS cluster placement groups do not span Availability Zones. 

Because low-latency collective communication depends on cluster placement locality, all benchmark nodes must be deployed within one AZ.

```mermaid

flowchart TB

  subgraph AWS["AWS Region"]

    subgraph AZ1["Availability Zone A (Selected)"]
      direction LR

      subgraph PG["Cluster Placement Group"]
        N1["GPU Node 1<br/>EFA"]
        N2["GPU Node 2<br/>EFA"]
        N3["GPU Node 3<br/>EFA"]
        N4["GPU Node 4<br/>EFA"]
      end

      N1 <-->|"RDMA Fabric"| N2
      N2 <-->|"RDMA Fabric"| N3
      N3 <-->|"RDMA Fabric"| N4
      N4 <-->|"RDMA Fabric"| N1
    end

    subgraph AZ2["Availability Zone B (Rejected)"]
      X1["GPU Node"]
    end

    X1 -.->|"Inter-AZ Traffic"| N1
  end

  classDef aws fill:#EAF3FF,stroke:#1F5FBF,stroke-width:2px,color:#0B1F44;
  classDef placement fill:#E8F5E9,stroke:#2E7D32,stroke-width:3px,color:#1B5E20;
  classDef node fill:#C8E6C9,stroke:#1B5E20,stroke-width:2px,color:#0D3B16;
  classDef rejected fill:#FDECEC,stroke:#D93025,stroke-width:3px,color:#7F1D1D;

  class PG placement;
  class N1,N2,N3,N4 node;
  class X1 rejected;

```

### 2. **Inter-AZ traffic bypasses the EFA fabric.**
> Traffic between nodes in different AZs routes through the AWS backbone network, not the EFA fabric. 

EFA-enabled MPI and NCCL workloads achieve the best latency and bandwidth when instances are co-located within a cluster placement group.

Deploying nodes across Availability Zones removes these locality guarantees and degrades collective communication performance.
 - adds ~500 µs of latency (vs ~15–25 µs on EFA) 
 - removes RDMA effectively degrading to TCP-over-Ethernet performance.


```mermaid
flowchart LR

    JOB["MPI / NCCL Benchmark Job"]

    JOB --> AZ["Single Availability Zone"]

    AZ --> PG["Cluster Placement Group"]

    PG --> N1["GPU Node 1<br/>EFA"]
    PG --> N2["GPU Node 2<br/>EFA"]
    PG --> N3["GPU Node 3<br/>EFA"]
    PG --> N4["GPU Node 4<br/>EFA"]

    MAZ["Multi-AZ Deployment"]
    MAZ -. Rejected .-> RPG["Separate Placement Groups"]
    RPG -.-> PERF["Loss of Fabric Locality"]
    PERF -.-> RESULT["Unpredictable Latency & Bandwidth"]

    classDef accepted fill:#E8F5E9,stroke:#2E7D32,stroke-width:3px,color:#1B5E20;
    classDef acceptedStrong fill:#C8E6C9,stroke:#1B5E20,stroke-width:4px,color:#0D3B16;
    classDef rejected fill:#FFF3E0,stroke:#EF6C00,stroke-width:3px,color:#E65100;
    classDef rejectedStrong fill:#FFEBEE,stroke:#C62828,stroke-width:4px,color:#B71C1C;
    classDef neutral fill:#F5F5F5,stroke:#616161,stroke-width:2px,color:#212121;

    class JOB neutral;
    class AZ,PG acceptedStrong;
    class N1,N2,N3,N4 accepted;
    class MAZ,RPG,PERF rejected;
    class RESULT rejectedStrong;

```

### 3. **EFA security group validation is local.** 
> EFA enforces that both endpoints of an RDMA connection belong to the same security group *and* are reachable within the cluster fabric.

Cross-AZ connections fail this check even if the SG is shared.

---
## ⚠️ Consequences

### AZ Bound
The caller must choose an AZ where the target instance type has capacity.

- Check before applying `p4d.24xlarge` capacity in specific AZ: 

  ```bash
  
  aws ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters Name=instance-type,Values=p4d.24xlarge \
    --region us-east-1 \
    --query 'InstanceTypeOfferings[].Location'
  
  ```

- `availability_zone` is a required variable in both `vpc-hpc` and `environments/dev`.

  
### Failure recovery
**Multi-AZ redundancy is not a goal for this benchmarking workload.** 
>If a node fails, the benchmark run is re-started, not failed over.

### Future Consideration:
If capacity shortages become frequent, evaluate Capacity Reservations
or Capacity Blocks for GPU instances within the selected AZ.

---

## Rejected alternatives

| Alternative                                    | Why rejected                                                                                                              |
|------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Multi-AZ with separate placement groups per AZ | Benchmark jobs span all nodes; a job cannot split cleanly across two placement groups without breaking the AllReduce ring |
| No placement group (AZ-flexible)               | Removes the fabric locality guarantee; nodes may end up on different spines with unpredictable latency and bandwidth      |
