module "research_storage" {
  source = "../../modules/research-storage"

  resource_group_name  = "rg-genomic-restore-study"
  location             = var.location
  storage_account_name = var.storage_account_name
  container_name       = "restore-lab"

  tags = {
    project     = "genomic-restore-study"
    environment = "research"
    managed_by  = "terraform"
  }
}
