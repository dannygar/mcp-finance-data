#!/usr/bin/env pwsh
# Start MCP Server with Azurite for local development

Write-Host "Starting MCP Finance Data Server..." -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error: Docker is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Check if Azurite container is already running
$azuriteRunning = docker ps --filter "ancestor=mcr.microsoft.com/azure-storage/azurite" --format "{{.ID}}"

if ($azuriteRunning) {
    Write-Host "Azurite is already running (container: $azuriteRunning)" -ForegroundColor Green
} else {
    # Check if there's a stopped Azurite container
    $azuriteStopped = docker ps -a --filter "ancestor=mcr.microsoft.com/azure-storage/azurite" --format "{{.ID}}" | Select-Object -First 1
    
    if ($azuriteStopped) {
        Write-Host "Starting existing Azurite container..." -ForegroundColor Yellow
        docker start $azuriteStopped | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to start Azurite container." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Starting Azurite storage emulator..." -ForegroundColor Yellow
        docker run -d -p 10000:10000 -p 10001:10001 -p 10002:10002 `
            --name tastytrade-azurite `
            mcr.microsoft.com/azure-storage/azurite | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to start Azurite." -ForegroundColor Red
            exit 1
        }
    }
    
    # Wait for Azurite to be ready
    Write-Host "Waiting for Azurite to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

Write-Host "Azurite is ready on ports 10000-10002" -ForegroundColor Green

# Sync dependencies if needed
if (-not (Test-Path ".venv")) {
    Write-Host "No virtual environment found. Running uv sync..." -ForegroundColor Yellow
    uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to sync dependencies." -ForegroundColor Red
        exit 1
    }
}

# Navigate to src directory and start Azure Functions
Write-Host "Starting Azure Functions MCP Server..." -ForegroundColor Yellow
Set-Location src

# Start the Functions host using uv run
uv run func start

# Cleanup on exit
$exitCode = $LASTEXITCODE
Set-Location ..

if ($exitCode -ne 0) {
    Write-Host "Azure Functions exited with error code $exitCode" -ForegroundColor Red
    exit $exitCode
}
