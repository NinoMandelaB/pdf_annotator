output "app_url" {
  value = "https://${azurerm_linux_web_app.pdf_annotator.default_hostname}"
}

output "resource_group_name" {
  value = azurerm_resource_group.pdf_annotator.name
}
