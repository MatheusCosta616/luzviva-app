variable "region" {
  type        = string
  default     = "sa-east-1" # Sao Paulo: dados pessoais ficam no Brasil (LGPD)
  description = "Regiao AWS"
}

variable "instance_type" {
  type    = string
  default = "t3.micro" # confira se o Learner Lab permite; alternativa: t2.micro
}

variable "instance_profile_name" {
  type        = string
  default     = ""
  description = "Perfil IAM opcional da EC2 (no Learner Lab: LabInstanceProfile)"
}

variable "image" {
  type        = string
  description = "Imagem do app no GHCR, ex.: ghcr.io/usuario/luzviva-app:latest (minusculo)"
}

variable "budget_limit_usd" {
  type        = number
  default     = 20
  description = "Teto mensal (USD) do alerta de orcamento"
}

variable "budget_email" {
  type        = string
  default     = ""
  description = "E-mail que recebe o alerta de orcamento (vazio = sem alerta)"
}
