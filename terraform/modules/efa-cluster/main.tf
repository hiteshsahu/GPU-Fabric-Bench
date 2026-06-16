locals {
  is_gpu_instance = can(regex("^p[0-9]", var.instance_type))
}

# GPU instances: Deep Learning AMI (CUDA + NCCL pre-installed)
# CPU instances: Amazon Linux 2 (EFA installed via user data)
data "aws_ami" "gpu" {
  count       = local.is_gpu_instance && var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning AMI GPU PyTorch*Amazon Linux 2*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "cpu" {
  count       = !local.is_gpu_instance && var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

locals {
  ami_id = var.ami_id != "" ? var.ami_id : (
    local.is_gpu_instance
    ? data.aws_ami.gpu[0].id
    : data.aws_ami.cpu[0].id
  )

  results_bucket = split(":::", var.s3_results_bucket_arn)[1]
}

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "cluster" {
  name = "${var.name}-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "s3_results" {
  name = "s3-results"
  role = aws_iam_role.cluster.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ]
      Resource = [
        var.s3_results_bucket_arn,
        "${var.s3_results_bucket_arn}/*"
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "cluster" {
  name = "${var.name}-cluster"
  role = aws_iam_role.cluster.name
  tags = var.tags
}

# Cluster placement group keeps all nodes on the same physical rack/spine
# for minimum fabric hops and maximum EFA bandwidth
resource "aws_placement_group" "cluster" {
  name     = "${var.name}-pg"
  strategy = "cluster"
  tags     = var.tags
}

data "aws_subnet" "cluster" {
  id = var.subnet_id
}

# Primary management NIC (eth0) — regular ENI, used for SSH and control plane
resource "aws_network_interface" "primary" {
  count           = var.node_count
  subnet_id       = var.subnet_id
  security_groups = var.security_group_ids
  tags            = merge(var.tags, { Name = "${var.name}-node-${count.index}-eth0" })
}

# EFA NICs (eth1..N) — EFA interface type enables RDMA and kernel bypass
# p4d.24xlarge: 4 EFA NICs; c5n.18xlarge: 1 EFA NIC
resource "aws_network_interface" "efa" {
  count             = var.node_count * var.efa_nic_count
  subnet_id         = var.subnet_id
  security_groups   = var.security_group_ids
  interface_type    = "efa"
  tags = merge(var.tags, {
    Name = "${var.name}-node-${floor(count.index / var.efa_nic_count)}-efa${count.index % var.efa_nic_count}"
  })
}

data "aws_ec2_instance_type" "this" {
  instance_type = var.instance_type
}

resource "aws_instance" "node" {
  count = var.node_count

  ami                  = local.ami_id
  instance_type        = var.instance_type
  key_name             = var.key_name
  placement_group      = aws_placement_group.cluster.id
  iam_instance_profile = aws_iam_instance_profile.cluster.name

  # Primary NIC attached here; EFA NICs attached separately below
  network_interface {
    network_interface_id = aws_network_interface.primary[count.index].id
    device_index         = 0
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 200
    encrypted   = true
  }

  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    results_bucket = local.results_bucket
    aws_region     = data.aws_region.current.name
  })

  tags = merge(var.tags, { Name = "${var.name}-node-${count.index}" })
}

# Attach EFA NICs to instances after creation (device_index 1..N)
resource "aws_network_interface_attachment" "efa" {
  count                = var.node_count * var.efa_nic_count
  instance_id          = aws_instance.node[floor(count.index / var.efa_nic_count)].id
  network_interface_id = aws_network_interface.efa[count.index].id
  device_index         = (count.index % var.efa_nic_count) + 1
}
