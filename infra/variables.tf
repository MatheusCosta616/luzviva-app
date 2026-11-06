variable "region" {
  type        = string
  default     = "us-east-1" # Learner Lab costuma liberar so us-east-1 / us-west-2 (confira no seu lab)
  description = "Regiao AWS"
}

variable "instance_type" {
  type    = string
  default = "t3.micro" # confira se o Learner Lab permite; alternativa: t2.micro
}

variable "instance_profile_name" {
  type    = string
  default = "LabInstanceProfile" # perfil pre-existente do Learner Lab
}

variable "image" {
  type        = string
  description = "Imagem do app no GHCR, ex.: ghcr.io/usuario/luzviva-app:latest (minusculo)"
}
