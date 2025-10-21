# Azure Deployment with Terraform

This directory contains Terraform configuration files for deploying the PDF Annotator application to Azure App Service.

⚠️ **Important Note**: This configuration has not been tested in production. Use at your own risk.

## Prerequisites

- Azure account (free tier available)
- Azure CLI installed
- Terraform installed (v1.0+ recommended)

## Files Included

- `main.tf`: Main Terraform configuration
- `variables.tf`: Variable definitions
- `outputs.tf`: Output definitions
- `terraform.tfvars`: Variable values (contains sensitive data)

## Required Adaptations

Before using this configuration, you must make the following changes:

1. **Secret Key**:
   - In `terraform.tfvars`, replace `your-very-secure-secret-key-here` with a real secret key
   - Do not commit sensitive values to version control

2. **Region and SKU**:
   - Current region: "West Europe" (change if needed)
   - Current SKU: "B1" (change to "F1" for free tier if preferred)

3. **GitHub Repository**:
   - Configuration already points to `https://github.com/NinoMandelaB/pdf_annotator`
   - If you fork this repository, update the URL in `main.tf`

## Deployment Process

1. Install Terraform and Azure CLI
2. Authenticate with Azure using `az login`
3. Run `terraform init` to initialize the configuration
4. Run `terraform plan` to review the execution plan
5. Run `terraform apply` to create the resources
6. After deployment, manually trigger the first deployment from Azure Portal:
   - Go to your new App Service
   - Navigate to Deployment Center
   - Click "Sync" to trigger the deployment

## Files Required in Repository Root

For this deployment to work, your repository must contain:
- `startup.txt` with: `gunicorn --bind=0.0.0.0 --workers=1 app:app`
- Updated `requirements.txt` including: `gunicorn==20.1.0`
- All application files (app.py, templates/, etc.)

## Cleanup

To remove all created resources when no longer needed:
terraform destroy


## Important Considerations

- The free tier (F1) has limited resources and may not be suitable for production
- The configuration uses basic settings appropriate for development/testing
- No database or storage configuration is included
- No custom domain or SSL configuration is provided
- No auto-scaling is configured

## Production Recommendations

For production environments, consider adding:
- Azure Key Vault for secure secret management
- Application Insights for monitoring
- Proper auto-scaling configuration
- CI/CD pipeline integration
- Security groups and network restrictions

## Support

This configuration is provided as-is without warranty. For issues:
1. Check Terraform output for error messages
2. Review Azure Portal logs
3. Verify all required files are present in your repository
