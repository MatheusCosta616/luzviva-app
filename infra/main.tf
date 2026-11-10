terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # State fora do Git (.gitignore). Aqui ele fica no AWS CloudShell, onde o apply roda.
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
  # Role propria com permissao minima (so le o token de deploy no SSM).
  # No Learner Lab, informe instance_profile_name = "LabInstanceProfile".
  iam_instance_profile = var.instance_profile_name == "" ? aws_iam_instance_profile.ec2.name : var.instance_profile_name

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  root_block_device {
    volume_size = 12
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    image       = var.image
    region      = var.region
    token_param = aws_ssm_parameter.deploy_token.name
  })
  user_data_replace_on_change = true

  tags = { Name = "luzviva-app", projeto = "gs-luzviva" }
}

# IP fixo: sem isso a URL muda quando a instancia para e volta.
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
}

# Alerta de custo: avisa em 80% do teto previsto e em 100% do gasto real.
resource "aws_budgets_budget" "mensal" {
  count        = var.budget_email == "" ? 0 : 1
  name         = "luzviva-mensal"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}

# ---------- Segredo de deploy ----------
# Gerado aqui, guardado cifrado no SSM Parameter Store (KMS) e copiado para o
# GitHub Secrets (DEPLOY_TOKEN). Nunca aparece no codigo nem na imagem.
resource "random_password" "deploy_token" {
  length  = 40
  special = false
}

resource "aws_ssm_parameter" "deploy_token" {
  name        = "/luzviva/deploy-token"
  description = "Token que o pipeline usa para confirmar o deploy"
  type        = "SecureString"
  value       = random_password.deploy_token.result
}

# ---------- IAM: a EC2 so pode ler esse parametro ----------
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name_prefix        = "luzviva-ec2-"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "ler_token" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.deploy_token.arn]
  }
}

resource "aws_iam_role_policy" "ler_token" {
  name   = "ler-token-deploy"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ler_token.json
}

resource "aws_iam_instance_profile" "ec2" {
  name_prefix = "luzviva-ec2-"
  role        = aws_iam_role.ec2.name
}
