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
