output "site_url" {
  description = "Public HTTPS URL of the storefront."
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "web_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "lambda_function_name" {
  value = aws_lambda_function.api.function_name
}

output "github_deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN variable in the GitHub production environment."
  value       = aws_iam_role.github_deploy.arn
}
