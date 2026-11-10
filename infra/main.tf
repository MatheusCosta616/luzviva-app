terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  # State LOCAL (arquivo terraform.tfstate fica fora do Git via .gitignore).
  # Learner Lab: guarde o state só na sua máquina e não apague a pasta antes do fim da correção.
}

provider "aws" {
  region = var.region
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# Sem porta 22: administração via SSM. Só o app (80) é público.
resource "aws_security_group" "app" {
  name_prefix = "luzviva-app-"
  description = "LuzViva: HTTP publico, sem SSH"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP do app (publico)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Saida liberada (pull de imagem, SSM)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  # Opcional: o deploy por pull nao precisa de permissao na AWS.
  # No Learner Lab, informe "LabInstanceProfile".
  iam_instance_profile = var.instance_profile_name == "" ? null : var.instance_profile_name

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  root_block_device {
    volume_size = 12
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", { image = var.image })

  tags = { Name = "luzviva-app", projeto = "gs-luzviva" }
}

# IP fixo: sem isso a URL muda quando a instancia para e volta.
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
}
