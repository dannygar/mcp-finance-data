# MCP Finance Data Server

Azure Functions-based MCP (Model Context Protocol) server providing company earnings data for AI agents.

## Architecture

- **Remote MCP server** using Azure Functions (Python 3.11+)
- **2 company earnings tools** for revenue and free cash flow analysis
- **Data provider**: Alpha Vantage API (SEC filings)
- **Supported companies**: Microsoft (MSFT), Tesla (TSLA), NVIDIA (NVDA)
- **Deployed via Azure Developer CLI** (`azd`)
- **Secured** with function keys and HTTPS

## Prerequisites

- **Python 3.11 or 3.12** (Azure Functions requirement - Python 3.13+ not yet supported)
- **Azure Functions Core Tools** >= 4.0.7030
- **Azure Developer CLI** (azd) for deployment

**Setup:**
```pwsh
# Configure uv to use Python 3.12 (required for Azure Functions)
uv python pin 3.12

# uv will automatically create .venv and install dependencies
uv sync
```

## Quick Start

### Local MCP Server (Azure Functions)

**Recommended:** Use the startup script (handles Azurite automatically):
```pwsh
.\start-mcp-server.ps1
```

**Manual start:**
```pwsh
# Start Azurite (if not already running)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 `
    --name finance-azurite `
    mcr.microsoft.com/azure-storage/azurite

# Sync dependencies (from root)
uv sync

# Navigate to src/
cd src

# Start Functions host (uv automatically uses correct Python version)
uv run func start

# Test SSE endpoint
# http://0.0.0.0:7071/runtime/webhooks/mcp/sse
```

**Note:** This project uses `uv` and `pyproject.toml` for dependency management. The `src/requirements.txt` file exists only for Azure Functions deployment (required by `azd`).

## Starting the MCP Server

### Option 1: Quick Start (Recommended)

Use the PowerShell script that handles everything automatically:

```pwsh
.\start-mcp-server.ps1
```

This script will:
- Check if Azurite is running and start it if needed
- Sync dependencies via `uv`
- Start the Azure Functions host on port 7071
- Make the MCP server available at `http://0.0.0.0:7071/runtime/webhooks/mcp/sse`

### Option 2: Manual Start

If you prefer manual control:

```pwsh
# 1. Start Azurite (if not already running)
docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 `
    --name finance-azurite `
    mcr.microsoft.com/azure-storage/azurite

# 2. Sync dependencies (from root)
uv sync

# 3. Navigate to src/
cd src

# 4. Start Functions host
uv run func start
```

The MCP server will be available at: `http://0.0.0.0:7071/runtime/webhooks/mcp/sse`

---

## Testing with MCP Inspector

The MCP Inspector is the official debugging tool for testing MCP servers.

### Setup

```pwsh
# Install dependencies (first time only)
yarn install
```

### Launch MCP Inspector

**Option 1: Combined Start (Easiest)**

Run the VS Code task that starts both the MCP server and inspector:

1. Press `Ctrl+Shift+P` (Windows) or `Cmd+Shift+P` (Mac)
2. Type "Tasks: Run Task"
3. Select "Start MCP Server + Inspector"

**Option 2: Manual Start**

Start the MCP server first, then launch the inspector:

```pwsh
# Terminal 1: Start MCP server
.\start-mcp-server.ps1

# Terminal 2: Launch inspector
yarn inspector
# or
.\run-inspector.ps1
```

The inspector opens a web UI at `http://localhost:5173` where you can:

- Browse available tools (`get_company_revenue`, `get_company_free_cash_flow`)
- Test tool invocations with custom parameters
- View request/response payloads in real-time
- Debug errors and validate tool outputs

**Note:** The inspector is pre-configured with the correct transport type (SSE) and URL parameters for quick testing.

---

## Verify Using GitHub Copilot

To verify your code, add the running project as an MCP server for GitHub Copilot in Visual Studio Code:

1. Press `F1`. In the command palette, search for and run **MCP: Add Server**.

2. Choose **HTTP (Server-Sent Events)** for the transport type.

3. Enter the URL of the MCP endpoint: `http://0.0.0.0:7071/runtime/webhooks/mcp/sse`

4. Use the generated Server ID and select **Workspace** to save the MCP server connection to your Workspace settings.

5. Open the command palette and run **MCP: List Servers** and verify that the server you added is listed and running.

6. In Copilot chat, select **Agent mode** and run this prompt:

   ```text
   What was Microsoft's revenue and free cash flow for Q4 FY2024?
   ```

The Copilot agent will use the `get_company_revenue` and `get_company_free_cash_flow` tools to fetch earnings data.

---

## Deploy to Azure

### 1. Configure API Keys

Before deploying, configure your API keys as environment variables:

```pwsh
# Required API key (minimum)
$env:ALPHAVANTAGE_API_KEY="your_alpha_vantage_key"

# Optional API keys (for enhanced features)
$env:FRED_API_KEY="your_fred_api_key"
$env:NEWSAPI_KEY="your_newsapi_key"
$env:FINNHUB_API_KEY="your_finnhub_key"
$env:RAPIDAPI_KEY="your_rapidapi_key"
```

**Where to get API keys:**
- **Alpha Vantage**: https://www.alphavantage.co/support/#api-key (Required - Free tier: 25 requests/day)
- **FRED**: https://fred.stlouisfed.org/docs/api/api_key.html (Optional - Free, for macroeconomic data)
- **NewsAPI**: https://newsapi.org/register (Optional - Free tier: 100 requests/day, for news headlines)
- **Finnhub**: https://finnhub.io/register (Optional - Free tier: 60 calls/minute, alternative market data)
- **RapidAPI**: https://rapidapi.com/ (Optional - Subscription required for social sentiment)

### 2. Deploy Infrastructure and Code

```pwsh
# Deploy infrastructure + code (will automatically include API keys)
azd up

# Or redeploy code only
azd deploy
```

**Important Configuration:**
- `.azure/gyc-dev/.env` must have `VNET_ENABLED="false"` (ensures storage network access is set to "Allow")
- Function key authentication is enabled by default (no EasyAuth)
- API keys are securely stored as Azure Function App settings during deployment

### 3. (Optional) Configure Microsoft Entra ID Authentication

**Note:** By default, the MCP server uses **function key authentication** which is simpler and works out of the box. Only run this script if you need OAuth/Entra ID authentication for your AI Foundry setup.

```pwsh
.\scripts\setup-auth.ps1 -AIFoundryManagedIdentityId <your-foundry-identity-id>
```

**What this script does:**
- Creates an Azure AD app registration with app role `Access.Function.MCP`
- Grants the app role to your AI Foundry managed identity
- Creates a client secret (180-day expiration)
- Adds Microsoft Graph User.Read permission
- Exposes API with `user_impersonation` scope
- **Keeps EasyAuth DISABLED** to preserve function key authentication

**Important:** 
- Save the client secret shown during setup - it won't be displayed again!
- EasyAuth remains **disabled** to avoid blocking function key requests
- The app registration is created but not enforced - use function keys for access

### 4. Teardown

```pwsh
# Remove all Azure resources
azd down
```

## MCP Tools

### Company Earnings Tools

#### `get_company_revenue`

Get total revenue in USD millions for a company's quarterly earnings report.

**Parameters:**
- `company_symbol` (string): Company ticker symbol (MSFT, TSLA, or NVDA)
- `fiscal_year` (number): Fiscal year (e.g., 2024)
- `fiscal_quarter` (number): Fiscal quarter (1, 2, 3, or 4)

**Returns:**
```json
{
  "company": "MSFT",
  "fiscal_year": 2024,
  "fiscal_quarter": 4,
  "fiscal_date_ending": "2024-06-30",
  "total_revenue_usd_millions": 64725.00,
  "currency": "USD",
  "data_source": "Alpha Vantage"
}
```

**Example Usage:**
```json
{
  "company_symbol": "MSFT",
  "fiscal_year": 2024,
  "fiscal_quarter": 4
}
```

---

#### `get_company_free_cash_flow`

Get free cash flow in USD millions for a company's quarterly earnings report.

**Parameters:**
- `company_symbol` (string): Company ticker symbol (MSFT, TSLA, or NVDA)
- `fiscal_year` (number): Fiscal year (e.g., 2024)
- `fiscal_quarter` (number): Fiscal quarter (1, 2, 3, or 4)

**Returns:**
```json
{
  "company": "MSFT",
  "fiscal_year": 2024,
  "fiscal_quarter": 4,
  "fiscal_date_ending": "2024-06-30",
  "free_cash_flow_usd_millions": 23255.00,
  "operating_cash_flow_usd_millions": 28515.00,
  "capital_expenditures_usd_millions": 5260.00,
  "currency": "USD",
  "data_source": "Alpha Vantage",
  "calculation": "Operating Cash Flow - Capital Expenditures"
}
```

**Example Usage:**
```json
{
  "company_symbol": "TSLA",
  "fiscal_year": 2024,
  "fiscal_quarter": 2
}
```

---

### Supported Companies

| Symbol | Company Name |
|--------|--------------|
| MSFT   | Microsoft Corporation |
| TSLA   | Tesla, Inc. |
| NVDA   | NVIDIA Corporation |

### Data Source

Both tools use the **Alpha Vantage API** to fetch real-time fundamental data:
- Revenue data: `INCOME_STATEMENT` endpoint
- Cash flow data: `CASH_FLOW` endpoint

The data is sourced directly from official SEC filings and updated regularly.

### Technical Details

**Free Cash Flow Calculation:**
```
Free Cash Flow = Operating Cash Flow - Capital Expenditures
```

Where:
- **Operating Cash Flow**: Cash generated from normal business operations
- **Capital Expenditures (CapEx)**: Cash spent on acquiring or maintaining fixed assets

This is a standard financial metric used to assess a company's ability to generate cash after accounting for capital investments.

**Fiscal Quarter Mapping:**

The tools automatically map fiscal quarters to calendar dates:
- **Q1**: September/October period end
- **Q2**: December/January period end
- **Q3**: March/April period end
- **Q4**: June/July period end

This mapping handles different companies' fiscal year calendars.

### Error Handling

The tools include comprehensive error handling:
- Invalid company symbol: Returns list of supported companies
- Invalid fiscal quarter: Returns acceptable range (1-4)
- Missing API key: Returns configuration instructions
- API failures: Returns detailed error message with troubleshooting guidance
- No data available: Falls back to most recent available quarter with warning

### Rate Limits

Alpha Vantage free tier:
- 25 requests per day
- 5 requests per minute

Consider upgrading for production use if needed.

## Debugging

### Debug Azure Functions (MCP Server)

#### Option 1: Auto-Start (Recommended)

The easiest way to debug the MCP server with full integration:

1. **Set breakpoints** in `src/function_app.py` where you want to inspect code
2. **Start debugging** with `F5` or select "Attach to Python Functions (Auto-Start)" from the Run and Debug panel
3. This automatically starts:
   - MCP Server (via `start-mcp-server.ps1`)
   - MCP Inspector (via `run-inspector.ps1`)
   - Debugger attachment to Python Functions on port 9091
4. **Trigger tools** via the MCP Inspector web UI (automatically opens at <http://localhost:5173>)
5. The debugger will pause at your breakpoints when tools are invoked

#### Option 2: Manual Start

For more control over the debugging process:

1. **Start MCP server** in a terminal: `.\start-mcp-server.ps1`
2. **Set breakpoints** in `src/function_app.py`
3. **Attach debugger**: Select "Attach to Python Functions (Manual)" from the Run and Debug panel and press `F5`
4. **Trigger tools** via MCP Inspector or any MCP client and hit breakpoints

#### Debugging Notes

- The Azure Functions host runs with **debugpy** on port **9091**
- **Auto-reload** is enabled - code changes automatically restart the function worker
- Watch applies to all `.py` files in the `src/` directory
- If you stop the MCP Inspector and see disposal errors, restart the MCP server with `.\start-mcp-server.ps1`



## Configuration

### Environment Variables

The project uses environment files in the `config/` directory:

- `config/.env.prod` - Production API keys (used when deployed to Azure)
- `config/.env.dev` - Development API keys (used for local testing)

**Required API Key:**

```env
ALPHAVANTAGE_API_KEY=your_alpha_vantage_key
```

**API Provider Details:**
- **Alpha Vantage**: Company fundamental data from SEC filings (INCOME_STATEMENT and CASH_FLOW endpoints). Free tier: 25 requests/day, 5 requests/minute. Get key at: https://www.alphavantage.co/support/#api-key

## Project Structure

```
├── src/
│   ├── function_app.py        # MCP server with company earnings tools
│   ├── requirements.txt       # Azure deployment only (generated from pyproject.toml)
│   ├── host.json              # Azure Functions config
│   └── local.settings.json    # Local development settings
├── infra/
│   ├── main.bicep             # Azure infrastructure
│   └── abbreviations.json     # Resource naming
├── config/
│   ├── .env.prod              # Production API keys
│   └── .env.dev               # Development API keys
├── docs/
│   └── AZURE_DEPLOYMENT.md    # Azure deployment guide
├── scripts/
│   └── setup-auth.ps1         # Azure authentication setup
├── azure.yaml                 # azd configuration
├── pyproject.toml             # uv/Python project config
├── package.json               # MCP Inspector dependencies
├── start-mcp-server.ps1       # Quick start script
├── run-inspector.ps1          # Launch MCP Inspector
└── .github/
    └── copilot-instructions.md
```

## Documentation

- [Build MCP Server with Azure Functions](https://learn.microsoft.com/en-us/azure/ai-foundry/mcp/build-your-own-mcp-server?view=foundry)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Azure Deployment Guide](docs/AZURE_DEPLOYMENT.md)

### API Provider Documentation

- [Alpha Vantage API](https://www.alphavantage.co/documentation/)
- [FRED API](https://fred.stlouisfed.org/docs/api/fred/)
- [NewsAPI Documentation](https://newsapi.org/docs)
- [Finnhub API](https://finnhub.io/docs/api)
- [CBOE Data](https://www.cboe.com/tradable_products/vix/)
- [GDELT 2.0 Documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [RapidAPI Marketplace](https://rapidapi.com/)


## Deploy to Azure for Remote MCP

Run this [azd](https://aka.ms/azd) command to provision the function app, with any required Azure resources, and deploy your code:

```shell
azd up
```

You can opt-in to a VNet being used in the sample. To do so, do this before `azd up`

```bash
azd env set VNET_ENABLED true
```

Additionally, [API Management]() can be used for improved security and policies over your MCP Server, and [App Service built-in authentication](https://learn.microsoft.com/azure/app-service/overview-authentication-authorization) can be used to set up your favorite OAuth provider including Entra.  

## Connect to your *remote* MCP server function app from a client

Your client will need a key in order to invoke the new hosted SSE endpoint, which will be of the form `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse`. The hosted function requires a system key by default which can be obtained from the [portal](https://learn.microsoft.com/azure/azure-functions/function-keys-how-to?tabs=azure-portal) or the CLI (`az functionapp keys list --resource-group <resource_group> --name <function_app_name>`). Obtain the system key named `mcp_extension`.

### Connect to remote MCP server in MCP Inspector
For MCP Inspector, you can include the key in the URL: 
```plaintext
https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<your-mcp-extension-system-key>
```

### Connect to remote MCP server in VS Code - GitHub Copilot
For GitHub Copilot within VS Code, you should instead set the key as the `x-functions-key` header in `mcp.json`, and you would just use `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse` for the URL. The following example uses an input and will prompt you to provide the key when you start the server from VS Code.  Note [mcp.json](.vscode/mcp.json) has already been included in this repo and will be picked up by VS Code.  Click Start on the server to be prompted for values including `functionapp-name` (in your /.azure/*/.env file) and `functions-mcp-extension-system-key` which can be obtained from CLI command above or API Keys in the portal for the Function App.  

```json
{
    "inputs": [
        {
            "type": "promptString",
            "id": "functions-mcp-extension-system-key",
            "description": "Azure Functions MCP Extension System Key",
            "password": true
        },
        {
            "type": "promptString",
            "id": "functionapp-name",
            "description": "Azure Functions App Name"
        }
    ],
    "servers": {
        "remote-mcp-function": {
            "type": "sse",
            "url": "https://${input:functionapp-name}.azurewebsites.net/runtime/webhooks/mcp/sse",
            "headers": {
                "x-functions-key": "${input:functions-mcp-extension-system-key}"
            }
        },
        "local-mcp-function": {
            "type": "sse",
            "url": "http://0.0.0.0:7071/runtime/webhooks/mcp/sse"
        }
    }
}
```

For MCP Inspector, you can include the key in the URL: `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<your-mcp-extension-system-key>`.

For GitHub Copilot within VS Code, you should instead set the key as the `x-functions-key` header in `mcp.json`, and you would just use `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse` for the URL. The following example uses an input and will prompt you to provide the key when you start the server from VS Code:

```json
{
    "inputs": [
        {
            "type": "promptString",
            "id": "functions-mcp-extension-system-key",
            "description": "Azure Functions MCP Extension System Key",
            "password": true
        }
    ],
    "servers": {
        "my-mcp-server": {
            "type": "sse",
            "url": "<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse",
            "headers": {
                "x-functions-key": "${input:functions-mcp-extension-system-key}"
            }
        }
    }
}
```

## Redeploy your code

You can run the `azd up` command as many times as you need to both provision your Azure resources and deploy code updates to your function app.

>[!NOTE]
>Deployed code files are always overwritten by the latest deployment package.

## Clean up resources

When you're done working with your function app and related resources, you can use this command to delete the function app and its related resources from Azure and avoid incurring any further costs:

```shell
azd down
```

## Helpful Azure Commands

Once your application is deployed, you can use these commands to manage and monitor your application:

```bash
# Get your function app name from the environment file
FUNCTION_APP_NAME=$(cat .azure/$(cat .azure/config.json | jq -r '.defaultEnvironment')/env.json | jq -r '.FUNCTION_APP_NAME')
echo $FUNCTION_APP_NAME

# Get resource group 
RESOURCE_GROUP=$(cat .azure/$(cat .azure/config.json | jq -r '.defaultEnvironment')/env.json | jq -r '.AZURE_RESOURCE_GROUP')
echo $RESOURCE_GROUP

# View function app logs
az webapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP

# Redeploy the application without provisioning new resources
azd deploy
```


## License

MIT
