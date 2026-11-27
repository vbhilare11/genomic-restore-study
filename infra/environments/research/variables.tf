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
