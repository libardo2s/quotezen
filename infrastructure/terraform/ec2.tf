resource "aws_iam_role" "lambda_role_quotezen" {
  name = "lambda-role-quotezen"

  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "lambda.amazonaws.com"
        },
        "Action" : "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_policy" "cognito_list_users_policy" {
  name        = "cognito-list-users-policy"
  description = "Allows Lambda execution role to list users in Cognito User Pool"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "cognito-idp:ListUsers"
        Resource = "arn:aws:cognito-idp:${var.aws_region}:${var.aws_account_number}:userpool/${aws_cognito_user_pool.user_pool_quotezen.id}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cognito_list_users_policy_attachment" {
  role       = aws_iam_role.lambda_role_quotezen.name
  policy_arn = aws_iam_policy.cognito_list_users_policy.arn
}


# Attach IAM policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_attachment" {
  role       = aws_iam_role.lambda_role_quotezen.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"  # Attach a read-only S3 access policy
}

resource "aws_db_instance" "posgtres_rds" {
  engine                 = "postgres"
  db_name                = var.db_name
  identifier             = "cfo"
  instance_class         = "db.t3.micro"
  engine_version         = "12"
  allocated_storage      = 20
  publicly_accessible    = true
  username               = var.db_username
  password               = var.db_password
  vpc_security_group_ids = [aws_security_group.security_group_ec2_quotezen.id]
  skip_final_snapshot    = true

  tags = {
    Name = "quotezen-db"
  }
}

output "endpoint" {
  value = aws_db_instance.posgtres_rds.endpoint
}

resource "aws_instance" "flask_ec2_quotezen" {
  ami                    = var.ami
  instance_type          = var.instance_type
  key_name               = var.ssh_key_pair_name
  associate_public_ip_address = true


  provisioner "remote-exec" {
    inline = [
      # Avoid unnecessary prompts
      "export DEBIAN_FRONTEND=noninteractive",

      # Update package list and install required packages
      "sudo apt-get update -y",
      "sudo apt-get install -y python3 python3-pip python3-venv git libpq-dev python3-dev",

      # Clone Flask application from GitHub
      "git clone ${var.github_repo} /home/ubuntu/flask_app",

      # Create and activate a virtual environment
      "python3 -m venv /home/ubuntu/flask_app/venv",

      # Upgrade pip within the virtual environment
      "/home/ubuntu/flask_app/venv/bin/pip install --upgrade pip",

      # Install Flask application dependencies
      "/home/ubuntu/flask_app/venv/bin/pip install -r /home/ubuntu/flask_app/app/requirements.txt",

      "/home/ubuntu/flask_app/venv/bin/pip install --upgrade gevent",

      # Allow traffic on port 5000
      "sudo ufw allow 5000",

      # Create a systemd service for Flask app
      "sudo bash -c 'cat > /etc/systemd/system/flask_app.service <<EOF",
      "[Unit]",
      "Description=Gunicorn instance to serve Flask application",
      "After=network.target",

      "[Service]",
      "User=ubuntu",
      "Group=ubuntu",
      "WorkingDirectory=/home/ubuntu/flask_app",
      "Environment=\"PATH=/home/ubuntu/flask_app/venv/bin\"",
      "Environment=\"AWS_ACCESS_KEY_ID=${var.accessKeyId}\"",
      "Environment=\"AWS_SECRET_ACCESS_KEY=${var.secretAccessKey}\"",
      "Environment=\"password_db=${var.db_password}\"",
      "Environment=\"db_endpoint=${aws_db_instance.posgtres_rds.endpoint}\"",
      "Environment=\"username_db=${var.db_username}\"",
      "Environment=\"COGNITO_KEYS_URL=${var.cognito_url_keys}\"",
      "Environment=\"HASH_KEY=${var.hash_key}\"",
      "Environment=\"db_name=${var.db_name}\"",
      "Environment=\"SES_SENDER_EMAIL=${var.sender_email}\"",
      "Environment=\"CLIENT_ID=${aws_cognito_user_pool_client.user_pool_client_quotezen.id}\"",
      "Environment=\"USER_POOL_ID=${aws_cognito_user_pool.user_pool_quotezen.id}\"",
      "ExecStart=/home/ubuntu/flask_app/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app.run:app",
      "Restart=always",

      "[Install]",
      "WantedBy=multi-user.target",
      "EOF'",

      # Reload systemd, start and enable the Flask app service
      "sudo systemctl daemon-reload",
      "sudo systemctl start flask_app",
      "sudo systemctl enable flask_app"
    ]

    connection {
      type        = "ssh"
      user        = "ubuntu"  # SSH username for Amazon Linux, CentOS, or Red Hat AMIs
      private_key = file(var.private_key_ec2_path)  # Replace with the path to your SSH private key file
      host        = self.public_ip
    }
  }

  tags = {
    Name = "quotezen_ec2"
  }

  vpc_security_group_ids = [aws_security_group.security_group_ec2_quotezen.id]

}

# **🔹 IAM Role para evitar credenciales en la instancia**
resource "aws_iam_role" "flask_role" {
  name = "flask_ec2_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_instance_profile" "flask_profile" {
  name = "flask_instance_profile"
  role = aws_iam_role.flask_role.name
}

resource "aws_security_group" "security_group_ec2_quotezen" {
  name        = "security_group_ec2_quotezen"
  description = "Security group for Flask EC2 instance"

  // Ingress rule to allow HTTP traffic from anywhere
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  // Allow traffic from any IPv4 address
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"   // Allow all protocols
    cidr_blocks     = ["0.0.0.0/0"]  // Allow traffic to any IPv4 address
  }
}