terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}

resource "azurerm_resource_group" "pdf_annotator" {
  name     = "pdf-annotator-rg"
  location = "West Europe"
}

resource "azurerm_service_plan" "pdf_annotator" {
  name                = "pdf-annotator-plan"
  resource_group_name = azurerm_resource_group.pdf_annotator.name
  location            = azurerm_resource_group.pdf_annotator.location
  os_type             = "Linux"
  sku_name            = "B1"  # Basic tier
}

resource "azurerm_linux_web_app" "pdf_annotator" {
  name                = "pdf-annotator-${random_string.random.result}"
  resource_group_name = azurerm_resource_group.pdf_annotator.name
  location            = azurerm_resource_group.pdf_annotator.location
  service_plan_id     = azurerm_service_plan.pdf_annotator.id

  site_config {
    application_stack {
      python_version = "3.9"
    }
    always_on = false
  }

  app_settings = {
    "SECRET_KEY" = var.secret_key
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    "WEBSITES_PORT" = "8000"
  }
}

resource "azurerm_app_service_source_control" "pdf_annotator" {
  app_id                 = azurerm_linux_web_app.pdf_annotator.id
  repo_url               = "https://github.com/NinoMandelaB/pdf_annotator"
  branch                 = "main"
  use_manual_integration = true
}
