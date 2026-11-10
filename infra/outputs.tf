output "app_ip" {
  value = aws_eip.app.public_ip
}

output "app_url" {
  value = "http://${aws_eip.app.public_ip}"
}

output "instance_id" {
  value       = aws_instance.app.id
  description = "ID da EC2 (para logs e diagnostico)"
}

output "deploy_token" {
  value       = random_password.deploy_token.result
  sensitive   = true
  description = "Copie para o GitHub Secrets como DEPLOY_TOKEN: terraform output -raw deploy_token"
}
