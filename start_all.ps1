$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runDir = Join-Path $projectRoot ".run"
$pidFile = Join-Path $runDir "service-pids.json"

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment not found at $pythonExe. Run 'uv sync' first."
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$ModuleName
    )

    $stdout = Join-Path $runDir "$Name.out.log"
    $stderr = Join-Path $runDir "$Name.err.log"

    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-m", $ModuleName) `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru

    [pscustomobject]@{
        Name = $Name
        ModuleName = $ModuleName
        Pid = $process.Id
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            Write-Host "$Name is ready at $Url"
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    throw "$Name did not become ready at $Url within $TimeoutSeconds seconds."
}

function Stop-StartedServices {
    param([array]$Services)

    foreach ($service in $Services) {
        try {
            Stop-Process -Id $service.Pid -ErrorAction Stop
        } catch {
        }
    }
}

$services = @()

try {
    Write-Host "Starting Registry service on port 10000..."
    $services += Start-ServiceProcess -Name "registry" -ModuleName "registry"
    Wait-HttpReady -Name "Registry" -Url "http://127.0.0.1:10000/health"

    Write-Host "Starting Tax Agent on port 10102..."
    $services += Start-ServiceProcess -Name "tax_agent" -ModuleName "tax_agent"
    Wait-HttpReady -Name "Tax Agent" -Url "http://127.0.0.1:10102/.well-known/agent.json"

    Write-Host "Starting Compliance Agent on port 10103..."
    $services += Start-ServiceProcess -Name "compliance_agent" -ModuleName "compliance_agent"
    Wait-HttpReady -Name "Compliance Agent" -Url "http://127.0.0.1:10103/.well-known/agent.json"

    Write-Host "Starting Law Agent on port 10101..."
    $services += Start-ServiceProcess -Name "law_agent" -ModuleName "law_agent"
    Wait-HttpReady -Name "Law Agent" -Url "http://127.0.0.1:10101/.well-known/agent.json"

    Write-Host "Starting Customer Agent on port 10100..."
    $services += Start-ServiceProcess -Name "customer_agent" -ModuleName "customer_agent"
    Wait-HttpReady -Name "Customer Agent" -Url "http://127.0.0.1:10100/.well-known/agent.json"

    $services | ConvertTo-Json | Set-Content -Path $pidFile

    Write-Host ""
    Write-Host "All services started:"
    Write-Host "  Registry:         http://127.0.0.1:10000"
    Write-Host "  Customer Agent:   http://127.0.0.1:10100"
    Write-Host "  Law Agent:        http://127.0.0.1:10101"
    Write-Host "  Tax Agent:        http://127.0.0.1:10102"
    Write-Host "  Compliance Agent: http://127.0.0.1:10103"
    Write-Host ""
    Write-Host "Logs and PID file are in .run\"
    Write-Host "Stop services with: .\stop_all.ps1"
} catch {
    Stop-StartedServices -Services $services
    throw
}
