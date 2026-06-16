## NCCL Benchmark

These tests check both the performance and the correctness of NCCL operations.

Run `all_reduce_perf` from 1K to 4G doubling each step, check 1, 20 iters 

the output looks like this:



```bash
============================================
NCCL AllReduce Benchmark
Nodes: 2 | GPUs/node: 8 | Total: 16
Timestamp: 20260616_143022
============================================

# nccl-tests allreduce_perf
# Using devices
#   Rank  0 Group  0 Pid  12301 on node-0 device  0 [0x10] NVIDIA A100-SXM4-80GB
#   Rank  1 Group  0 Pid  12302 on node-0 device  1 [0x10] NVIDIA A100-SXM4-80GB
#   ...
#   Rank 15 Group  0 Pid  12309 on node-1 device  7 [0x10] NVIDIA A100-SXM4-80GB

#
#                                                              out-of-place                       in-place
#       size         count      type   redop    root    time   algbw   busbw #wrong   time   algbw   busbw #wrong
#        (B)    (elements)                               (us)  (GB/s)  (GB/s)          (us)  (GB/s)  (GB/s)
        1024           256     float     sum      -1    28.43    0.04    0.07      0    27.91    0.04    0.07      0
        2048           512     float     sum      -1    28.61    0.07    0.13      0    28.14    0.07    0.13      0
        4096          1024     float     sum      -1    29.02    0.14    0.26      0    28.87    0.14    0.27      0
        8192          2048     float     sum      -1    29.44    0.28    0.52      0    29.21    0.28    0.53      0
       16384          4096     float     sum      -1    30.17    0.54    1.02      0    29.98    0.55    1.03      0
       32768          8192     float     sum      -1    32.43    1.01    1.90      0    32.11    1.02    1.91      0
       65536         16384     float     sum      -1    36.88    1.78    3.33      0    36.54    1.79    3.36      0
      131072         32768     float     sum      -1    44.21    2.97    5.56      0    43.97    2.98    5.59      0
      262144         65536     float     sum      -1    58.74    4.47    8.37      0    58.31    4.50    8.43      0
      524288        131072     float     sum      -1    87.32    6.00   11.25      0    86.91    6.03   11.30      0
     1048576        262144     float     sum      -1   158.43    6.62   12.41      0   157.88    6.64   12.45      0
     2097152        524288     float     sum      -1   241.17    8.70   16.31      0   240.54    8.72   16.35      0
     4194304       1048576     float     sum      -1   392.88   10.68   20.02      0   391.44   10.71   20.08      0
     8388608       2097152     float     sum      -1   622.14   13.48   25.28      0   620.87   13.51   25.33      0
    16777216       4194304     float     sum      -1   892.11   18.81   35.27      0   889.44   18.87   35.38      0
    33554432       8388608     float     sum      -1  1487.32   22.56   42.30      0  1483.91   22.61   42.40      0
    67108864      16777216     float     sum      -1  2743.88   24.45   45.85      0  2739.44   24.49   45.92      0
   134217728      33554432     float     sum      -1  5291.44   25.37   47.57      0  5284.32   25.40   47.63      0
   268435456      67108864     float     sum      -1 10432.17   25.73   48.25      0 10419.88   25.76   48.30      0
   536870912     134217728     float     sum      -1 18432.14   29.13   54.62      0 18401.22   29.18   54.71      0
  1073741824     268435456     float     sum      -1 36218.43   29.65   55.59      0 36190.11   29.67   55.63      0   
  2147483648     536870912     float     sum      -1 72104.88   29.78   55.84      0 72088.41   29.79   55.85      0
  4294967296    1073741824     float     sum      -1 143891.22  29.85   55.97      0 143844.71   29.86   55.98     0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 31.42 GB/s

Results saved: benchmarks/nccl/results/allreduce_20260616_143022.txt
```

Key things to read:

| Column	       | Meaning                                                                                                            |
|---------------|--------------------------------------------------------------------------------------------------------------------|
| size (B)	     | Message size per rank                                                                                              |
| time (us)     | 	Collective latency : Wall-clock time for the collective                                                           |
| algbw (GB/s)	 | Algorithm bandwidth size / time — what the app sees                                                                |
| busbw (GB/s)	 | Effective fabric bandwidth algbw × 2(N-1)/N — actual fabric utilization; compare this to NIC peak (50 GB/s on EFA) |
| #wrong	       | Validation failures:  Correctness check (--check 1) — must be 0                                                    |


### Expected result

What the shape tells you on EFA:

- Small messages (`< 1 MB`) — latency-bound, `busbw` climbs slowly
- Large messages (`≥ 64 MB`) — bandwidth-bound, `busbw` plateaus near ~55 GB/s (~90% of `400 Gb/s` EFA on `p4d` with 4
  NICs)
- The summary line Avg bus bandwidth: `31.42 GB/s` 