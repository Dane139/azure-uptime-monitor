variable "yourname" {
  type = string
}
 
variable "location" {
  type    = string
  default = "Central US"
}
 
variable "target_url" {
  description = "The website URL to monitor. Include https://."
  type        = string
}
 
variable "alert_email" {
  description = "Email address for downtime alerts."
  type        = string
}
 
variable "alert_phone" {
  description = "Phone number for SMS alerts in E.164 format (e.g. +14045550100)."
  type        = string
}
 
variable "tags" {
  type = map(string)
  default = {
    project    = "uptime-monitor"
    managed_by = "terraform"
  }
}
