resource "aws_instance" "bizagi_app" {
  ami                    = var.ec2_ami
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.app_server.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
              #!/bin/bash
              # Update system
              apt-get update -y
              apt-get upgrade -y
              
              # Install dependencies
              apt-get install -y python3-pip python3-dev python3-venv libpq-dev postgresql-client nginx git
              
              # Clone your application
              git clone https://github.com/libardo2s/quotezen.git /opt/bizagi
              cd /opt/bizagi
              
              # Create virtual environment
              python3 -m venv venv
              source venv/bin/activate
              
              # Install Python requirements
              pip install -r requirements.txt
              
              # Create .env file with database connection
              cat <<EOT > /opt/bizagi/.env
              DB_HOST=${aws_db_instance.postgresql.endpoint}
              DB_PORT=5432
              DB_NAME=${var.db_name}
              DB_USER=${var.db_username}
              DB_PASSWORD=${var.db_password}
              FLASK_ENV=production
              SECRET_KEY=your-secret-key-here
              EOT
              
              # Set proper permissions
              chmod 600 /opt/bizagi/.env
              chown -R ubuntu:ubuntu /opt/bizagi
              
              # Initialize database
              python database.py create_all
              
              # Configure nginx
              cat <<EOT > /etc/nginx/sites-available/bizagi
              server {
                  listen 80;
                  server_name _;
                  
                  location / {
                      proxy_pass http://127.0.0.1:5000;
                      proxy_set_header Host \$host;
                      proxy_set_header X-Real-IP \$remote_addr;
                  }
              }
              EOT
              
              ln -s /etc/nginx/sites-available/bizagi /etc/nginx/sites-enabled
              rm /etc/nginx/sites-enabled/default
              
              # Start services
              systemctl restart nginx
              
              # Run application
              sudo -u ubuntu nohup /opt/bizagi/venv/bin/python /opt/bizagi/app.py > /var/log/bizagi.log 2>&1 &
              EOF

  tags = {
    Name = "${var.app_name}-app-server"
  }

  depends_on = [aws_db_instance.postgresql]
}