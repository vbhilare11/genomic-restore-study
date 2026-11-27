variable "subscription_id" {
  description = "Personal Azure subscription used for this research."
  type        = string
  nullable    = false
}

variable "tenant_id" {
  description = "Microsoft Entra tenant containing the personal subscription."
  type        = string
  nullable    = false
}

variable "storage_account_name" {
  description = "Globally unique name for the research storage account."
  type        = string
}

variable "location" {
  description = "Azure region for the research environment."
  type        = string
  default     = "eastus2"
}
