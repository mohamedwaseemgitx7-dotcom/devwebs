variable "region" {
  description = "AWS region for Lambda and S3 (CloudFront is global)."
  type        = string
  default     = "ap-south-1" # Mumbai: closest to Indian users
}

variable "env" {
  description = "Environment name."
  type        = string
  default     = "prod"
}

variable "name" {
  description = "Resource name prefix."
  type        = string
  default     = "flashcart"
}

variable "lambda_zip_path" {
  description = "Path to the API deployment package built by CI (app + Linux arm64 dependencies)."
  type        = string
  default     = "../../build/flashcart-api-lambda.zip"
}

variable "lambda_memory_mb" {
  description = "Lambda memory. 512 MB keeps cold starts short and stays far inside the free tier at demo traffic."
  type        = number
  default     = 512
}

variable "lambda_reserved_concurrency" {
  description = "Concurrency cap (cost and Atlas M0 connection guard). -1 = unreserved: new accounts have a total quota of 10, which cannot be reserved."
  type        = number
  default     = -1
}

variable "log_retention_days" {
  description = "CloudWatch log retention. Short to stay inside the 5 GB free log storage."
  type        = number
  default     = 7
}

variable "budget_email" {
  description = "Email that receives AWS Budgets alerts."
  type        = string
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in USD. Any spend at all is unexpected for this project."
  type        = string
  default     = "1"
}

variable "github_repo" {
  description = "owner/repo allowed to deploy via GitHub OIDC (main branch only)."
  type        = string
  default     = "mohamedwaseemgitx7-dotcom/devwebs"
}

variable "create_github_oidc_provider" {
  description = "Create the account-wide GitHub OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}

# ---- Secrets: supplied via TF_VAR_* environment variables or an untracked tfvars file, never committed ----

variable "mongodb_uri" {
  description = "MongoDB Atlas connection string."
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret (>= 32 chars)."
  type        = string
  sensitive   = true
}

variable "webhook_secret" {
  description = "Webhook HMAC secret (>= 32 chars)."
  type        = string
  sensitive   = true
}

variable "metrics_token" {
  description = "Bearer token for /metrics (>= 32 chars)."
  type        = string
  sensitive   = true
}
