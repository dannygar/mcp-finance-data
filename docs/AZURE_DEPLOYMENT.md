# Azure Deployment Guide - Market Intelligence MCP Server

This guide walks you through deploying the Market Intelligence MCP Server to Azure Functions and configuring Microsoft Entra ID authentication for secure access from Azure AI Foundry agents.

## Overview

Azure AI Foundry requires authenticated access to MCP servers. Your MCP server is deployed as an Azure Function with:
- **11 market intelligence tools** for AI agents to access market data, macroeconomic indicators, volatility indices, news, calendars, and social sentiment
- **User-assigned managed identity** for Azure resource access
- **Function key authentication** for API access (default)
- **Support for Microsoft Entra ID authentication** (to be configured)
- **Multiple data providers** including Alpha Vantage, Finnhub, FRED, CBOE, NewsAPI, GDELT, and RapidAPI

## Prerequisites

- Azure Functions MCP server deployed via `azd up`
- Azure AI Foundry project created
- Azure CLI installed and authenticated
- Owner or User Access Administrator role on the subscription
- **Required API keys** configured in `config/.env.prod`:
  - `ALPHAVANTAGE_API_KEY` - Alpha Vantage API key
  - `FRED_API_KEY` - FRED (Federal Reserve Economic Data) API key
  - `NEWSAPI_KEY` - NewsAPI key
- **Optional API keys** for enhanced functionality:
  - `FINNHUB_API_KEY` - Finnhub API key (fallback for market data)
  - `RAPIDAPI_KEY` - RapidAPI key (required for social sentiment analysis)

## Step 0: Configure API Keys

Before deployment, ensure all required API keys are configured. You have two options:

### Option A: Environment Variables (Recommended for CI/CD)

Set the API keys as environment variables before running `azd up`:

```pwsh
# Required API key (minimum)
$env:ALPHAVANTAGE_API_KEY="your_alpha_vantage_key"

# Optional API keys (for enhanced features)
$env:FRED_API_KEY="your_fred_api_key"
$env:NEWSAPI_KEY="your_newsapi_key"
$env:FINNHUB_API_KEY="your_finnhub_key"
$env:RAPIDAPI_KEY="your_rapidapi_key"

# Deploy with API keys
azd up
```

The deployment will automatically read these environment variables and securely deploy them to your Azure Function App.

### Option B: Manual Configuration (After Deployment)

If you prefer to configure API keys after deployment, you can add them manually:

```pwsh
# Get your function app name and resource group
$functionAppName = azd env get-values | Select-String "AZURE_FUNCTION_NAME" | ForEach-Object { ($_ -split '=')[1].Trim('"') }
$resourceGroup = azd env get-values | Select-String "AZURE_RESOURCE_GROUP_NAME" | ForEach-Object { ($_ -split '=')[1].Trim('"') }

# Set API keys as app settings
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroup --settings `
  "ALPHAVANTAGE_API_KEY=your_alpha_vantage_key" `
  "FRED_API_KEY=your_fred_api_key" `
  "NEWSAPI_KEY=your_newsapi_key" `
  "FINNHUB_API_KEY=your_finnhub_key" `
  "RAPIDAPI_KEY=your_rapidapi_key"
```

**Where to get API keys:**
- Alpha Vantage: https://www.alphavantage.co/support/#api-key (Required - Free tier: 25 requests/day)
- FRED: https://fred.stlouisfed.org/docs/api/api_key.html (Optional - Free, for macroeconomic data)
- NewsAPI: https://newsapi.org/register (Optional - Free tier: 100 requests/day, for news headlines)
- Finnhub: https://finnhub.io/register (Optional - Free tier: 60 calls/minute, alternative market data)
- RapidAPI: https://rapidapi.com/ (Optional - Subscription required for social sentiment)

**Note**: The MCP server requires at minimum `ALPHAVANTAGE_API_KEY`. All other keys are optional and enable additional tools and features.

## Step 1: Get Your Function App Details

```pwsh
# Get your deployment outputs
azd env get-values

# Note the following values:
# - AZURE_FUNCTION_NAME: Your function app name
# - AZURE_LOCATION: Deployment region
# - AZURE_TENANT_ID: Your tenant ID
```

Or retrieve them directly:

```pwsh
# Get function app name
$functionAppName = az functionapp list --query "[?tags.\"azd-env-name\"=='<your-env-name>'].name" -o tsv

# Get resource group
$resourceGroup = az functionapp list --query "[?name=='$functionAppName'].resourceGroup" -o tsv

echo "Function App: $functionAppName"
echo "Resource Group: $resourceGroup"
```

## Step 2: Enable Microsoft Entra ID Authentication

### Automated Setup (Recommended)

Run the provided setup script which automatically creates an app registration and configures authentication:

```pwsh
# Option 1: Set up authentication only (assign app role later)
.\scripts\setup-auth.ps1

# Option 2: Set up authentication AND grant app role to AI Foundry identity
.\scripts\setup-auth.ps1 -AIFoundryManagedIdentityId <principal-id>
```

This script will:
- Create an Azure AD app registration with workforce configuration
- Configure multi-tenant authentication (AzureADMultipleOrgs)
- Create a client secret with 180-day expiration
- Add **App Role** "Access.Function.MCP" for service-to-service authentication
- Configure "Allow requests from any application" (no pre-authorization required)
- Add Microsoft Graph User.Read delegated permission
- Expose API with `user_impersonation` scope
- Configure Function App authentication (HTTP 401 for unauthenticated requests)
- Enable token store
- Update `WEBSITE_AUTH_PRM_DEFAULT_WITH_SCOPES` app setting
- **Optionally** grant app role to AI Foundry managed identity (if provided)

**Save the client secret displayed during setup!**

**Script Parameters:**
- `-EnvironmentName`: azd environment name (default: "gyc-dev")
- `-ClientSecretExpirationDays`: Secret expiration in days (default: 180)
- `-AIFoundryManagedIdentityId`: AI Foundry managed identity principal ID (optional)

### Manual Setup (Alternative)

If you prefer manual configuration:

#### Option A: Using Azure Portal

1. Navigate to your Function App in the Azure Portal
2. Go to **Settings** → **Authentication**
3. Click **Add identity provider**
4. Select **Microsoft**
5. Configure:
   - **Configuration**: Workforce configuration
   - **App registration**: Create new app registration
   - **Name**: Same as function app name
   - **Client secret expiration**: 180 days
   - **Supported account types**: Multi-tenant
   - **Client application requirement**: Allow requests from any application
   - **Allow requests from any identity**: Yes
   - **Issuer restriction**: Use default restrictions based on issuer
   - **Restrict access**: Require authentication
   - **Unauthenticated requests**: HTTP 401 Unauthorized
   - **Token store**: Enabled
6. Add **User.Read** delegated permission
7. Click **Add**

#### Option B: Using Azure CLI

See `scripts/setup-auth.ps1` for the complete CLI implementation.

## Step 3: Grant Azure AI Foundry Access

Your Azure AI Foundry project needs permission to call your MCP server.

### Get AI Foundry Managed Identity

```pwsh
# List your AI Foundry resources (they are Cognitive Services accounts of kind AIServices)
az cognitiveservices account list --query "[].{name:name, kind:kind, resourceGroup:resourceGroup, location:location}" -o table

# Or list in a specific resource group
az cognitiveservices account list --resource-group <your-resource-group> --query "[].{name:name, kind:kind}" -o table

# Get the managed identity of your AI Foundry resource
$aiFoundryName = "<your-ai-foundry-resource-name>"
$aiProjectRg = "<your-ai-foundry-resource-group>"

# Get the managed identity principal ID
$aiProjectIdentity = az cognitiveservices account show `
  --name $aiFoundryName `
  --resource-group $aiProjectRg `
  --query identity.principalId -o tsv

echo "AI Foundry Identity: $aiProjectIdentity"
```

### Grant App Role (Recommended Method)

If you didn't use the `-AIFoundryManagedIdentityId` parameter during initial setup, grant the app role now:

```pwsh
# Re-run setup script with AI Foundry identity to grant app role
.\scripts\setup-auth.ps1 -AIFoundryManagedIdentityId $aiProjectIdentity
```

This grants the **Access.Function.MCP** application permission to the AI Foundry managed identity, enabling service-to-service authentication without user context.

### Alternative: Assign Azure RBAC Role

Alternatively, you can grant Azure RBAC permissions (less secure, grants broader access):

```pwsh
# Assign Website Contributor role to allow function invocation
az role assignment create `
  --assignee $aiProjectIdentity `
  --role "Website Contributor" `
  --scope $functionAppId

echo "Role assignment completed"
```

> **Note**: The app role method (recommended) provides fine-grained access control specific to your MCP server. The RBAC method grants broader management permissions but may be required in some scenarios.

## Step 4: Configure MCP Connection in Azure AI Foundry

### Get Your MCP Endpoint URL

```pwsh
$mcpEndpoint = "https://$functionAppName.azurewebsites.net/runtime/webhooks/mcp/sse"
echo "MCP Endpoint: $mcpEndpoint"
```

### Add MCP Server to AI Foundry

**Option A: Using Azure AI Foundry Studio**

1. Navigate to your AI Foundry project: https://ai.azure.com
2. Go to **Agent** → **Tools** → **MCP Servers**
3. Click **Add MCP Server**
4. Configure:
   - **Name**: `tastytrade-mcp`
   - **Transport Type**: HTTP (Server-Sent Events)
   - **Endpoint URL**: `https://<your-function-app>.azurewebsites.net/runtime/webhooks/mcp/sse`
   - **Authentication**: Microsoft Entra ID
   - **Audience**: Your function app URL
5. Click **Save**

**Option B: Using Python SDK**

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Initialize AI Project client
project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str="<your-ai-foundry-connection-string>"
)

# Add MCP server connection
mcp_config = {
    "name": "tastytrade-mcp",
    "transport_type": "sse",
    "endpoint": "https://<your-function-app>.azurewebsites.net/runtime/webhooks/mcp/sse",
    "authentication": {
        "type": "entra_id",
        "audience": "https://<your-function-app>.azurewebsites.net"
    }
}

# Register the MCP server (API varies by SDK version)
# Check latest documentation at https://learn.microsoft.com/azure/ai-studio/
```

## Step 5: Configure Environment Variables in Function App

Your Tastytrade credentials need to be in the Function App:

```pwsh
# Set credentials as app settings (secure)
az functionapp config appsettings set `
  --name $functionAppName `
  --resource-group $resourceGroup `
  --settings "ACCOUNT=<your-tastytrade-username>" "PASSWORD=<your-tastytrade-password>"
```

**Better: Use Azure Key Vault (Recommended)**

```pwsh
# Create Key Vault
$keyVaultName = "kv-tastytrade-$((Get-Random -Maximum 9999).ToString('0000'))"
az keyvault create `
  --name $keyVaultName `
  --resource-group $resourceGroup `
  --location $AZURE_LOCATION

# Store secrets
az keyvault secret set --vault-name $keyVaultName --name "TASTYTRADE-ACCOUNT" --value "<your-username>"
az keyvault secret set --vault-name $keyVaultName --name "TASTYTRADE-PASSWORD" --value "<your-password>"

# Get managed identity of function app
$functionIdentity = az functionapp identity show `
  --name $functionAppName `
  --resource-group $resourceGroup `
  --query principalId -o tsv

# Grant function app access to Key Vault
az keyvault set-policy `
  --name $keyVaultName `
  --object-id $functionIdentity `
  --secret-permissions get list

# Update function app to use Key Vault references
$accountRef = "@Microsoft.KeyVault(SecretUri=https://$keyVaultName.vault.azure.net/secrets/TASTYTRADE-ACCOUNT/)"
$passwordRef = "@Microsoft.KeyVault(SecretUri=https://$keyVaultName.vault.azure.net/secrets/TASTYTRADE-PASSWORD/)"

az functionapp config appsettings set `
  --name $functionAppName `
  --resource-group $resourceGroup `
  --settings "ACCOUNT=$accountRef" "PASSWORD=$passwordRef"
```

## Step 6: Test the Connection

### Test from Azure Portal

1. Go to your Function App → **Functions** → Any MCP function
2. Click **Test/Run**
3. Verify authentication works

### Test MCP Connection

```pwsh
# Get an access token
$token = az account get-access-token --resource "https://$functionAppName.azurewebsites.net" --query accessToken -o tsv

# Test the MCP endpoint
curl -H "Authorization: Bearer $token" "https://$functionAppName.azurewebsites.net/runtime/webhooks/mcp/sse"
```

### Test from AI Foundry Agent

Create a test agent in AI Foundry and run:

```
Give me the list of all transactions for today
```

The agent should call your `get_transactions` MCP tool and return results.

## Step 7: Update Infrastructure as Code (Optional)

To make authentication permanent in your deployment, update `infra/app/api.bicep`:

```bicep
// Add after existing parameters
@description('Enable Microsoft Entra ID authentication')
param enableEntraAuth bool = true

@description('Tenant ID for authentication')
param tenantId string = tenant().tenantId

// Add to the api module params
module api 'br/public:avm/res/web/site:0.15.1' = {
  params: {
    // ... existing params ...
    
    authSettingV2Configuration: enableEntraAuth ? {
      globalValidation: {
        requireAuthentication: true
        unauthenticatedClientAction: 'Return401'
      }
      identityProviders: {
        azureActiveDirectory: {
          enabled: true
          registration: {
            openIdIssuer: 'https://login.microsoftonline.com/${tenantId}/v2.0'
            clientId: name
          }
          validation: {
            allowedAudiences: [
              'https://${name}.azurewebsites.net'
            ]
          }
        }
      }
    } : null
  }
}
```

Then redeploy:

```pwsh
azd deploy
```

## Troubleshooting

### Error: "401 Unauthorized"

- Verify Entra ID authentication is enabled
- Check that AI Foundry identity has proper role assignment
- Confirm audience matches your function app URL

### Error: "403 Forbidden"

- Verify role assignment: `az role assignment list --assignee $aiProjectIdentity --scope $functionAppId`
- Ensure "Azure Functions Invoker" or "Website Contributor" role is assigned

### Error: "MCP server not responding"

- Check function app logs: `az functionapp log tail --name $functionAppName --resource-group $resourceGroup`
- Verify environment variables are set correctly
- Test with function key first to isolate auth vs. application issues

### Error: "InternalServerError" when testing MCP tools

This usually indicates the Python runtime is not properly configured:

```pwsh
# Check if Python runtime is configured
az functionapp config show --name $functionAppName --resource-group $resourceGroup --query "{linuxFxVersion:linuxFxVersion}" -o json

# If linuxFxVersion is empty or null, configure it manually:
# Via Azure Portal: Configuration → General settings → Stack: Python 3.12
# Or redeploy with: azd up
```

**Common causes:**
- Python runtime version not set (should be `PYTHON|3.12`)
- Missing or incorrect `requirements.txt` in `src/` directory
- Deployment failed to install dependencies
- Function app needs restart after configuration change

### Error: "Missing environment variables"

- Verify `ACCOUNT` and `PASSWORD` are set in app settings
- If using Key Vault, check managed identity has access
- View current settings: `az functionapp config appsettings list --name $functionAppName --resource-group $resourceGroup`

## Security Best Practices

1. **Use Key Vault** for sensitive credentials (not app settings)
2. **Enable managed identity** for all Azure resource access
3. **Use least privilege roles** (Azure Functions Invoker instead of Contributor)
4. **Enable logging** for authentication failures
5. **Rotate credentials regularly** in Key Vault
6. **Use private endpoints** if deploying in production (already configured with `vnetEnabled=true`)

## Next Steps

- Configure CORS if accessing from web applications
- Set up Application Insights for monitoring
- Configure auto-scaling based on usage
- Add custom domains and SSL certificates

## References

- [Azure Functions Authentication](https://learn.microsoft.com/azure/azure-functions/functions-authentication)
- [Azure AI Foundry MCP Integration](https://learn.microsoft.com/azure/ai-studio/how-to/configure-mcp-servers)
- [Managed Identity Best Practices](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/overview)
- [Azure Key Vault Integration](https://learn.microsoft.com/azure/app-service/app-service-key-vault-references)
