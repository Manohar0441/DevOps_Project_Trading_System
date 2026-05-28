terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "s3" {
    bucket = "trading-devops-tf-state"
    key    = "infra/terraform.tfstate"
    region = "ap-south-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "trading-devops"
}

variable "environment" {
  type    = string
  default = "prod"
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  services = toset([
    "batch-service",
    "frontend-service",
    "notification-service",
    "portfolio-service",
    "risk-service",
    "scoring-service",
    "screening-service",
  ])
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

# ---------------------------------------------------------------------------
# ECR — one repository per service
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "service" {
  for_each = local.services

  name                 = "${var.project_name}/${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
module "vpc" {
  source = "./modules/vpc"

  project_name         = var.project_name
  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  availability_zones   = local.azs
}

# ---------------------------------------------------------------------------
# IAM roles for EKS
# ---------------------------------------------------------------------------
module "iam" {
  source = "./modules/iam"

  project_name   = var.project_name
  sqs_queue_arns = module.sqs.queue_arns
}

# ---------------------------------------------------------------------------
# EKS cluster
# ---------------------------------------------------------------------------
module "eks" {
  source = "./modules/eks"

  project_name       = var.project_name
  kubernetes_version = "1.32"
  cluster_role_arn   = module.iam.cluster_role_arn
  node_role_arn      = module.iam.node_role_arn
  private_subnet_ids = module.vpc.private_subnet_ids
  desired_nodes      = 2
  min_nodes          = 1
  max_nodes          = 4
  instance_type      = "t3.small"
}

# ---------------------------------------------------------------------------
# SQS queues (screening events → risk events → notification events)
# ---------------------------------------------------------------------------
module "sqs" {
  source = "./modules/sqs"

  project_name = var.project_name
  queue_names  = ["screening-events", "risk-events", "notification-events"]
}

# ---------------------------------------------------------------------------
# S3 — scoring outputs and batch artifacts
# ---------------------------------------------------------------------------
module "s3" {
  source = "./modules/s3"

  project_name  = var.project_name
  bucket_suffix = random_id.bucket_suffix.hex
}

# ---------------------------------------------------------------------------
# ElastiCache Redis — score caching
# ---------------------------------------------------------------------------
module "elasticache" {
  source = "./modules/elasticache"

  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  vpc_cidr           = "10.0.0.0/16"
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type          = "cache.t3.micro"
  num_cache_clusters = 1
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "ecr_repositories" {
  description = "ECR repository URLs per service"
  value       = { for name, repo in aws_ecr_repository.service : name => repo.repository_url }
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint (inject into K8s ConfigMap)"
  value       = module.elasticache.redis_endpoint
}

output "sqs_queue_urls" {
  description = "SQS queue URLs per queue name (inject into K8s ConfigMap)"
  value       = module.sqs.queue_urls
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}
