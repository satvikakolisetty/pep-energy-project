# Global Variables

variable "aws_region" {
  description = "AWS region where all the resources will be created."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project to prefix the resource names"
  type        = string
  default     = "pep-energy" 
}