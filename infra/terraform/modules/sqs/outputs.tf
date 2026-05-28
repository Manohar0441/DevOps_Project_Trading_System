output "queue_urls" {
  value = { for k, q in aws_sqs_queue.main : k => q.url }
}

output "queue_arns" {
  value = [for q in aws_sqs_queue.main : q.arn]
}
