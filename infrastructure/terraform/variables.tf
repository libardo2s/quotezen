variable "app_name" {
  description = "Application name used for naming resources"
  type        = string
  default     = "bizagi"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Database variables
variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "bizagidb"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

# EC2 variables
variable "ec2_ami" {
  description = "AMI ID for EC2 instance"
  type        = string
  default     = "ami-0f9de6e2d2f067fca" # Ubuntu 20.04 LTS
}

variable "ec2_instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "ssh_key_name" {
  description = "Name of existing SSH key pair"
  type        = string
  default     = "bizagi-key"
}