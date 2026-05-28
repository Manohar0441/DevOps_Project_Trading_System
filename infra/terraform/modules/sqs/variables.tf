variable "project_name" {
  type = string
}

variable "queue_names" {
  type    = list(string)
  default = ["screening-events", "risk-events", "notification-events"]
}
