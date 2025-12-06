# AI coding agent guide for this repo

## Big picture
- Purpose: Azure Functions-based MCP (Model Context Protocol) server providing company earnings data for AI agents.
- Architecture: Remote MCP server using Azure Functions with Python 3.11+, deployed via Azure Developer CLI (azd).
- Key modules:
  - `src/function_app.py`: MCP server with 2 company earnings tools:
    - get_company_revenue: Get quarterly revenue in USD millions (via Alpha Vantage INCOME_STATEMENT)
    - get_company_free_cash_flow: Get quarterly free cash flow in USD millions (via Alpha Vantage CASH_FLOW)
  - Supported companies: Microsoft (MSFT), Tesla (TSLA), NVIDIA (NVDA)
- Config/secrets live in `config/.env.dev` and `config/.env.prod`; loaded explicitly by path.
- Required API key: ALPHAVANTAGE_API_KEY only
- Infrastructure: `infra/main.bicep` defines Azure resources (Function App, Storage, App Insights); `azure.yaml` configures azd deployment.

## Runtime & workflows (Windows/PowerShell)
- Python: 3.11 or 3.12 (Azure Functions requirement; 3.13+ not yet supported). Uses `uv` for dependency management.
- Local MCP server (Azure Functions):
  - **Easy start**: `.\start-mcp-server.ps1` (handles Azurite + Functions automatically)
  - **Manual start**:
    - Start Azurite: `docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 --name azurite mcr.microsoft.com/azure-storage/azurite`
    - Sync dependencies: `uv sync` (from root)
    - Navigate to `src/`: `cd src`
    - Start Functions host: `uv run func start` (uv handles Python version automatically)
  - Test SSE endpoint: `http://0.0.0.0:7071/runtime/webhooks/mcp/sse`
  - Connect via MCP Inspector (`yarn inspector`) or VS Code Copilot agent mode
  - Note: `src/requirements.txt` exists only for Azure deployment; use `uv` for local dev
- MCP Inspector testing:
  - Install: `yarn install`
  - Start server: `.\start-mcp-server.ps1`
  - Launch inspector: `yarn inspector` or `.\run-inspector.ps1` (opens web UI at http://localhost:5173)
  - Test tools interactively with custom parameters and view request/response payloads
- Deploy to Azure:
  - Set environment variable: `$env:ALPHAVANTAGE_API_KEY="your_key"`
  - Initialize: `azd init` (if not already done)
  - Deploy: `azd up` (provisions infrastructure + deploys code)
  - Redeploy code only: `azd deploy`
  - Teardown: `azd down`
- No formal test suite; validation via running tools and observing logs.
- Debugging:
  - Azure Functions: F5 or "Attach to Python Functions" config, debugpy on port 9091
  - Breakpoints work in all Python files

## Environment configuration
Use explicit `.env` files under `config/`:

| Environment | File | Usage |
|---|---|---|
| Local | `config/.env.dev` | Local development and testing
| Azure | `config/.env.prod` | Azure deployment (automatically detected via `WEBSITE_INSTANCE_ID`)

Tip: The MCP server automatically detects Azure environment and switches to `.env.prod`. For local development, it always uses `.env.dev`.

## Secrets and configuration
- Required env var in `config/.env.*`:
  - `ALPHAVANTAGE_API_KEY` - for company earnings data (INCOME_STATEMENT and CASH_FLOW endpoints)
- Pattern (replicate when adding scripts):
  - Compute `project_root` from the file location
  - Build `env_path = os.path.join(project_root, 'config', '.env.prod')` (or `.env.dev`)
  - `load_dotenv(dotenv_path=env_path)`
- `src/test.py` writes a `remember-token` to `sessions/session_token.txt`; treat it as sensitive.

Accounts: assume a single Tastytrade account. If needed, store the account number in `ACCOUNT_NUMBER` in your `.env.*`. You can discover it once via `/customers/me/accounts` using `tasty.api.get`.

## SDK and API usage patterns
- Preferred library: `tastytrade_sdk` (see `requirements.txt`).
  - Login: `tasty = Tastytrade().login(login=username, password=password)`
  - Market data subscription: `tasty.market_data.subscribe(symbols=[...], on_quote=..., on_candle=..., on_greeks=...)`; call `subscription.open()` and later `subscription.close()`.
  - Direct REST calls for gaps: `tasty.api.get('/path', params=...)`.
    - For endpoints requiring repeated params (e.g., `symbol[]`, `account-number[]`), pass a list of tuples: `[('symbol[]', 'SPX'), ('symbol[]', 'VIX')]`.
- Sandbox vs prod:
  - SDK default base URL is prod (`api.tastytrade.com`).
  - Use sandbox/cert by constructing `Tastytrade(api_base_url='api.cert.tastyworks.com')`.
  - `src/test.py` demonstrates direct `requests` calls to cert endpoints without the SDK (historical/diagnostic use).
  
  Docs:
  - SDK (GitHub): https://github.com/tastytrade/tastytrade-sdk-python
  - API reference: https://tastytrade.github.io/tastytrade-sdk-python/tastytrade_sdk.html

## Project conventions to follow
- Always load `.env` via an explicit path under `config/`; do not rely on implicit `.env` in CWD.
- Use `logging` with `basicConfig(level=logging.INFO)` for script logs.
- Compute paths relative to the script’s directory to work from any CWD.
- Keep secrets out of code; access via env only.

## Typical task templates (examples)
- Add a new script under `src/`:
  1) Load env from `config/.env.prod` (or `.env.dev`)
  2) Login with `Tastytrade().login(...)`
  3) Make API calls with try-except error handling
  4) Return JSON response using `json.dumps()`
- Example: Adding a new market data tool:
  - Define tool properties: `ToolProperty("symbol", "string", "Ticker symbol")`
  - Add trigger: `@app.generic_trigger(arg_name="context", type="mcpToolTrigger", toolName="get_data", ...)`
  - Load environment: `_load_env()`
  - Get API key: `api_key = _get_env("SOME_API_KEY")`
  - Make request: `resp = requests.get(url, params=params, timeout=10)`
  - Return result: `return json.dumps({"data": resp.json()}, indent=2)`

## API Provider Details
- **Alpha Vantage**: Market data for stocks, ETFs, indices. Free tier: 25 requests/day, 5 requests/minute.
- **FRED**: Federal Reserve economic data. Free with API key, generous rate limits.
- **NewsAPI**: News headlines from 150k+ sources. Free tier: 100 requests/day, developer plan required.
- **Finnhub**: Stock market data and news. Free tier: 60 calls/minute.
- **CBOE**: Volatility indices (VIX, VVIX, SKEW). Public CSV downloads, no rate limits.
- **GDELT**: Global media monitoring. Public API, no auth, max ~200 records per query.
- **ForexFactory/FiveThirtyEight**: Web scraping (HTML), use respectful User-Agent, avoid excessive requests.
- **RapidAPI**: Aggregated marketplace for social sentiment APIs. Requires subscription, rate limits vary by endpoint. Use for Reddit, StockTwits, news sentiment, and optionally Twitter (use with caution due to ToS concerns).

## Debugging tips
- Missing API key errors: Check `.env` file has all required keys with actual values (not "your-key")
- HTTP 401/403: Verify API key is valid and not expired
- Rate limit errors: Respect provider limits, implement caching if needed
- If `dotenv` doesn't load, check the computed `env_path` and file name used
