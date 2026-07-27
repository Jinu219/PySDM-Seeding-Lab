[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidatePattern('^cloud[0-9]+$')]
    [string]$Target = 'cloud7',

    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$Branch = 'develop',

    [ValidatePattern('^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+$')]
    [string]$Gateway = 'jwlee@10.125.114.179',

    [ValidateRange(1, 65535)]
    [int]$GatewayPort = 18901,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Invoke-Native {
    param(
        [Parameter(Mandatory)]
        [string]$Command,

        [Parameter(ValueFromRemainingArguments)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

$projectRoot = (Invoke-Native git rev-parse --show-toplevel | Select-Object -Last 1).Trim()
Set-Location -LiteralPath $projectRoot

$currentBranch = (Invoke-Native git branch --show-current | Select-Object -Last 1).Trim()
if ($currentBranch -ne $Branch) {
    throw "Expected local branch '$Branch', but the current branch is '$currentBranch'."
}

Invoke-Native git check-ref-format --branch $Branch | Out-Null

$trackedChanges = @(git status --porcelain --untracked-files=no)
$unexpectedChanges = @(
    $trackedChanges | Where-Object {
        $_ -and $_.Substring(3) -ne 'configs/default.yaml'
    }
)
if ($unexpectedChanges.Count -gt 0) {
    Write-Warning 'Uncommitted tracked changes are not included in a Git bundle:'
    $unexpectedChanges | ForEach-Object { Write-Warning "  $_" }
    throw 'Commit the changes intended for deployment, then run this command again.'
}

$commit = (Invoke-Native git rev-parse --short HEAD | Select-Object -Last 1).Trim()
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$deploymentId = "$Branch-$commit-$timestamp"
$runtimeDir = Join-Path $projectRoot '.runtime\deploy'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$bundleName = "pysdm-$deploymentId.bundle"
$applyName = "apply-pysdm-$deploymentId.sh"
$bundlePath = Join-Path $runtimeDir $bundleName
$applySource = Join-Path $projectRoot 'scripts\apply_server_bundle.sh'
$remoteBundle = "/tmp/$bundleName"
$remoteApply = "/tmp/$applyName"

Invoke-Native git bundle create $bundlePath "refs/heads/$Branch"
Invoke-Native git bundle verify $bundlePath

Write-Host "Prepared deployment: $Branch $commit -> $Target"
if ($DryRun) {
    Write-Host "Dry run only. Bundle: $bundlePath"
    exit 0
}

try {
    Write-Host 'Uploading bundle through cloud0...'
    Invoke-Native scp -P "$GatewayPort" $bundlePath $applySource "${Gateway}:/tmp/"

    $gatewayCommand = @(
        "set -e"
        "mv /tmp/apply_server_bundle.sh '$remoteApply'"
        "scp '$remoteBundle' '$remoteApply' '${Target}:/tmp/'"
        "ssh '$Target' bash '$remoteApply' '$remoteBundle' '$Branch'"
        "sleep 2"
        "ssh '$Target' 'cd ~/PySDM-Seeding-Lab && bash scripts/server_web.sh status && curl --noproxy \* --fail --silent --show-error --max-time 5 http://127.0.0.1:8501/_stcore/health && echo'"
        "rm -f '$remoteBundle' '$remoteApply'"
    ) -join '; '

    Write-Host "Applying and restarting on $Target..."
    Invoke-Native ssh -t -p "$GatewayPort" $Gateway $gatewayCommand
}
finally {
    if (Test-Path -LiteralPath $bundlePath) {
        Remove-Item -LiteralPath $bundlePath -Force
    }
}
