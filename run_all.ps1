param(
    [string]$PythonPath = "C:\Users\Manohar\AppData\Local\Programs\Python\Python310\python.exe",
    [string]$HostAddress = "127.0.0.1",
    [int]$ScoringPort = 8000,
    [int]$FrontendPort = 8080
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendBuildPath = Join-Path $projectRoot "services\frontend_service\static\index.html"

if (-not (Test-Path $PythonPath)) {
    throw "Python executable not found at: $PythonPath"
}

if (-not (Test-Path $frontendBuildPath)) {
    throw "Frontend build not found. Run the React build first from services/frontend_service/webapp."
}

$env:SCORING_SERVICE_HOST = $HostAddress
$env:SCORING_SERVICE_PORT = [string]$ScoringPort
$env:FRONTEND_SERVICE_HOST = $HostAddress
$env:FRONTEND_SERVICE_PORT = [string]$FrontendPort

$commands = @(
    @{
        Name = "Scoring Service"
        Command = "& '$PythonPath' -m services.scoring_service.server"
    },
    @{
        Name = "Frontend Service"
        Command = "& '$PythonPath' -m services.frontend_service.server"
    }
)

$jobs = @()

try {
    foreach ($service in $commands) {
        $job = Start-Job -Name $service.Name -ScriptBlock {
            param($root, $command, $scoringHost, $scoringPortValue, $frontendHost, $frontendPortValue)

            Set-Location $root
            $env:SCORING_SERVICE_HOST = $scoringHost
            $env:SCORING_SERVICE_PORT = $scoringPortValue
            $env:FRONTEND_SERVICE_HOST = $frontendHost
            $env:FRONTEND_SERVICE_PORT = $frontendPortValue
            Invoke-Expression $command
        } -ArgumentList @(
            $projectRoot,
            $service.Command,
            $env:SCORING_SERVICE_HOST,
            $env:SCORING_SERVICE_PORT,
            $env:FRONTEND_SERVICE_HOST,
            $env:FRONTEND_SERVICE_PORT
        )

        $jobs += $job
    }

    Write-Host ""
    Write-Host "Services started:" -ForegroundColor Green
    Write-Host "  Scoring API : http://$HostAddress`:$ScoringPort/health"
    Write-Host "  Frontend    : http://$HostAddress`:$FrontendPort/"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both services."
    Write-Host ""

    while ($true) {
        foreach ($job in $jobs) {
            if ($job.State -eq "Failed") {
                Receive-Job -Job $job -Keep
                throw "$($job.Name) failed."
            }

            if ($job.State -eq "Completed") {
                $output = Receive-Job -Job $job
                if ($output) {
                    $output | Out-Host
                }
                throw "$($job.Name) exited unexpectedly."
            }
        }

        Start-Sleep -Seconds 2
    }
}
finally {
    foreach ($job in $jobs) {
        if ($null -ne $job) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue | Out-Null
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
        }
    }
}
