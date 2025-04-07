output "ec2_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.bizagi_app.public_ip
}

output "ec2_public_dns" {
  description = "Public DNS of the EC2 instance"
  value       = aws_instance.bizagi_app.public_dns
}

output "db_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgresql.endpoint
}

output "application_url" {
  description = "Application URL"
  value       = "http://${aws_instance.bizagi_app.public_dns}"
}