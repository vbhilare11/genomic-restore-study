variable "resource_group_name" {
  description = "Resource group dedicated to the research infrastructure."
  type        = string
}

variable "location" {
  description = "Azure region for the research resources."
  type        = string
}

variable "storage_account_name" {
  description = "Globally unique storage account name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Use 3–24 lowercase letters or digits."
  }
}

variable "container_name" {
  description = "Private container for research datasets."
  type        = string
  default     = "restore-lab"
}

variable "tags" {
  description = "Resource ownership and purpose tags."
  type        = map(string)
  default     = {}
}
