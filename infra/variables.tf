variable "region" {
  type        = string
  default     = "us-east-1"
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
