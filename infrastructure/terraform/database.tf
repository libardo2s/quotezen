resource "aws_db_subnet_group" "default" {
  name       = "${var.app_name}-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  
  tags = {
    Name = "${var.app_name}-db-subnet-group"
  }
}

resource "aws_db_parameter_group" "postgresql" {
  name   = "${var.app_name}-postgres14-params"
  family = "postgres14"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_db_instance" "postgresql" {
  identifier             = "${var.app_name}-db"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100
  engine                 = "postgres"
  engine_version         = "14.15"
  username               = var.db_username
  password               = var.db_password
  db_name                = var.db_name
  
  db_subnet_group_name   = aws_db_subnet_group.default.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false
  
  backup_retention_period = 7
  skip_final_snapshot    = false
  final_snapshot_identifier = "${var.app_name}-final-snapshot"
  
  parameter_group_name   = aws_db_parameter_group.postgresql.name
  storage_encrypted      = true
  deletion_protection    = false

  tags = {
    Name = "${var.app_name}-postgresql"
  }
}