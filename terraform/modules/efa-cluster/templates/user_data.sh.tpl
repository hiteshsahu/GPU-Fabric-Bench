#!/bin/bash
set -euo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

# ── EFA driver ──────────────────────────────────────────────────────────────
cd /tmp
curl -sO https://efa-installer.amazonaws.com/aws-efa-installer-latest.tar.gz
tar -xf aws-efa-installer-latest.tar.gz && cd aws-efa-installer
sudo ./efa_installer.sh -y
source /etc/profile.d/efa.sh

# ── OpenMPI (if not present from DLAMI) ─────────────────────────────────────
if ! command -v mpirun &>/dev/null; then
  cd /tmp
  curl -sO https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.6.tar.gz
  tar -xf openmpi-4.1.6.tar.gz && cd openmpi-4.1.6
  ./configure --prefix=/opt/openmpi --with-libfabric=/opt/amazon/efa \
              --enable-mpirun-prefix-by-default
  make -j$(nproc) && sudo make install
  echo 'export PATH=/opt/openmpi/bin:$PATH' | sudo tee /etc/profile.d/openmpi.sh
  echo 'export LD_LIBRARY_PATH=/opt/openmpi/lib:$LD_LIBRARY_PATH' >> /etc/profile.d/openmpi.sh
  source /etc/profile.d/openmpi.sh
fi

# ── OSU micro-benchmarks ────────────────────────────────────────────────────
cd /tmp
curl -sO https://mvapich.cse.ohio-state.edu/download/mvapich/osu-micro-benchmarks-7.3.tar.gz
tar -xf osu-micro-benchmarks-7.3.tar.gz && cd osu-micro-benchmarks-7.3
./configure CC=mpicc CXX=mpicxx --prefix=/opt/osu
make -j$(nproc) && sudo make install
echo 'export PATH=/opt/osu/libexec/osu-micro-benchmarks/mpi/pt2pt:$PATH' | \
  sudo tee /etc/profile.d/osu.sh

# ── NCCL tests (GPU instances only) ─────────────────────────────────────────
if command -v nvcc &>/dev/null; then
  CUDA_HOME=$(dirname $(dirname $(which nvcc)))
  NCCL_HOME=/usr/local/nccl

  # aws-ofi-nccl plugin: bridges NCCL → libfabric → EFA
  cd /tmp
  git clone https://github.com/aws/aws-ofi-nccl.git
  cd aws-ofi-nccl
  ./autogen.sh
  ./configure \
    --with-mpi=/opt/openmpi \
    --with-libfabric=/opt/amazon/efa \
    --with-nccl=$${NCCL_HOME} \
    --with-cuda=$${CUDA_HOME}
  make -j$(nproc) && sudo make install

  # nccl-tests
  cd /tmp
  git clone https://github.com/NVIDIA/nccl-tests.git
  cd nccl-tests
  make MPI=1 MPI_HOME=/opt/openmpi \
       NCCL_HOME=$${NCCL_HOME} \
       CUDA_HOME=$${CUDA_HOME} \
       -j$(nproc)
  sudo cp build/* /usr/local/bin/
fi

# ── NCCL environment defaults ────────────────────────────────────────────────
cat <<'EOF' | sudo tee /etc/profile.d/nccl-efa.sh
export NCCL_IB_HCA=efa
export NCCL_SOCKET_IFNAME=efa
export FI_EFA_USE_DEVICE_RDMA=1
export FI_EFA_FORK_SAFE=1
export NCCL_ALGO=Ring
export NCCL_PROTO=Simple
EOF

# ── MPI hostfile placeholder (updated by Ansible or init script) ──────────────
echo "$(hostname -I | awk '{print $1}') slots=8" | sudo tee /etc/nccl_hostfile

# ── Signal readiness ─────────────────────────────────────────────────────────
aws s3 cp /dev/null s3://${results_bucket}/init/$(hostname)-ready \
  --region ${aws_region} || true

echo "user-data complete: $(date)"
