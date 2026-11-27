output "resource_group_name" {
  description = "Research resource group name."
  value       = azurerm_resource_group.this.name
}

output "storage_account_id" {
  description = "Storage account resource ID."
  value       = azurerm_storage_account.this.id
}

output "storage_account_name" {
  description = "Storage account name."
  value       = azurerm_storage_account.this.name
}

output "container_name" {
  description = "Private research container name."
  value       = azurerm_storage_container.this.name
}

output "blob_endpoint" {
  description = "Blob service endpoint."
  value       = azurerm_storage_account.this.primary_blob_endpoint
}
