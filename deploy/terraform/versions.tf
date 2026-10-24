terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.68.0" # exact pin, >= 14 days old (ADR-004)
    }
    random = {
      source  = "hashicorp/random"
      version = "3.7.2"
    }
  }

  # State stays local (gitignored) until the owner approves an S3 state bucket. State contains secrets
  # (origin-verify header, Lambda env), so it must never be committed.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "flashcart"
      ManagedBy = "terraform"
      Env       = var.env
    }
  }
}

data "aws_caller_identity" "current" {}
