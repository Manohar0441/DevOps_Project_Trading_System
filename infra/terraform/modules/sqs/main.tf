resource "aws_sqs_queue" "dlq" {
  for_each = toset(var.queue_names)

  name                      = "${var.project_name}-${each.key}-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = { Name = "${var.project_name}-${each.key}-dlq" }
}

resource "aws_sqs_queue" "main" {
  for_each = toset(var.queue_names)

  name                      = "${var.project_name}-${each.key}"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400 # 24 hours
  receive_wait_time_seconds = 20    # long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.project_name}-${each.key}" }
}
