variable "project_name" {
  type = string
}

variable "sqs_queue_arns" {
  type    = list(string)
  default = []
}
