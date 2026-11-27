output "research_storage" {
  description = "Research storage identifiers; contains no access keys."
  value = {
    resource_group_name  = module.research_storage.resource_group_name
    storage_account_name = module.research_storage.storage_account_name
    storage_account_id   = module.research_storage.storage_account_id
    container_name       = module.research_storage.container_name
    blob_endpoint        = module.research_storage.blob_endpoint
  }
}
