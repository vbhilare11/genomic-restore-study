data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "research_blob_access" {
  scope                = module.research_storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
