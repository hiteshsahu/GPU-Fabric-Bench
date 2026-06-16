## OSU latency benchmark

The OSU Micro-Benchmarks (OMB) are the industry-standard suite used in High-Performance Computing (HPC) to evaluate network fabric performance, specifically Message Passing Interface (MPI) latency and bandwidth. 

Maintained by The **Ohio State University**, the benchmark measures the time it takes (in microseconds, $μs$) to send a message between a sender and receiver and wait for a reply (ping-pong).

The osu_latency benchmark produces this output format:


```bash
# OSU MPI Latency Test v7.3
# Size          Latency (us)
0                       1.92
1                       1.94
2                       1.95
4                       1.96
8                       1.97
16                      1.99
32                      2.03
64                      2.11
128                     2.28
256                     2.61
512                     3.28
1024                    4.62
2048                    7.31
4096                   12.68
8192                   23.41
16384                  44.87
32768                  87.93
65536                 175.21
131072                349.88
262144                699.14
524288               1398.03
1048576              2795.61
```

| Column       | Data                                              |
|--------------|---------------------------------------------------|
| Left column  | message size in bytes                             |
| Right column | one-way latency in microseconds (half round-trip) |

Each row is the median of N iterations (default 1000 warmup + 10000 measured)

### Expected result
On EFA (`c5n.18xlarge`) you'd expect `~15–25` µs at small message sizes. 

On physical IB (NDR) it'd be `~1–2 µs`. 

If you see anything above `~100 µs` at small sizes, NCCL/MPI has fallen back to TCP.