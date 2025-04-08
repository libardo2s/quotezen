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
              set -e  # Exit immediately on error
              exec > >(tee /var/log/user-data.log) 2>&1  # Log all output
              
              # Update system
              apt-get update -y
              apt-get upgrade -y
              
              # Install specific Python version and venv package
              PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
              apt-get install -y python${PYTHON_VERSION}-venv python3-pip python3-dev libpq-dev postgresql-client nginx git
              
              # Clone your application
              git clone https://github.com/libardo2s/quotezen.git /opt/bizagi
              cd /opt/bizagi
              
              # Create virtual environment with explicit Python path
              python3 -m venv --system-site-packages venv || {
                echo "Virtual environment creation failed"
                python3 -m pip install virtualenv
                virtualenv venv
              }
              source venv/bin/activate
              
              # Install Python requirements
              pip install --upgrade pip
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
              
              # Initialize database with retries
              for i in {1..5}; do
                python database.py create_all && break || sleep 10
              done
              
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
              rm -f /etc/nginx/sites-enabled/default
              
              # Start services
              systemctl restart nginx
              
              # Create systemd service for better process management
              cat <<EOT > /etc/systemd/system/bizagi.service
              [Unit]
              Description=Bizagi Flask Application
              After=network.target
              
              [Service]
              User=ubuntu
              WorkingDirectory=/opt/bizagi
              Environment="PATH=/opt/bizagi/venv/bin"
              ExecStart=/opt/bizagi/venv/bin/python /opt/bizagi/app.py
              Restart=always
              
              [Install]
              WantedBy=multi-user.target
              EOT
              
              systemctl daemon-reload
              systemctl enable bizagi.service
              systemctl start bizagi.service
              EOF

  tags = {
    Name = "${var.app_name}-app-server"
  }

  depends_on = [aws_db_instance.postgresql]
}