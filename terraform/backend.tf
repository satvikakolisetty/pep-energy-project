# This file configures Terraform to use a remote S3 backend.
terraform {
  backend "s3" {
    bucket         = "pep-energy-terraform-state-file"
    key            = "pep-energy/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"       # The table for state locking.
    encrypt        = true
  }
}