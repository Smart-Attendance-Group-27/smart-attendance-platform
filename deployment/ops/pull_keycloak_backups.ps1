param(
    [string]$SshHost = 'uniattend-vps',
    [string]$Destination = (Join-Path $env:USERPROFILE '.uniattend-backups')
)

$ErrorActionPreference = 'Stop'
$remoteDirectory = '/opt/uniattend/backups'

if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
    throw "Protected backup directory is missing: $Destination"
}

$entries = & ssh -o BatchMode=yes $SshHost "sha256sum $remoteDirectory/keycloak-*.dump.age"
if ($LASTEXITCODE -ne 0) {
    throw 'Could not list and hash encrypted Keycloak backups on the VPS.'
}

foreach ($entry in $entries) {
    if ($entry -notmatch '^([0-9a-f]{64})  (/opt/uniattend/backups/(keycloak-[0-9TZ-]+\.dump\.age))$') {
        throw "Unexpected remote backup manifest entry: $entry"
    }

    $expectedHash = $Matches[1]
    $remotePath = $Matches[2]
    $name = $Matches[3]
    $localPath = Join-Path $Destination $name

    if ((Test-Path -LiteralPath $localPath -PathType Leaf) -and
        (Get-FileHash -LiteralPath $localPath -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expectedHash) {
        Write-Output "Verified $name"
        continue
    }

    $temporary = "$localPath.download"
    try {
        & scp -B -q "${SshHost}:$remotePath" $temporary
        if ($LASTEXITCODE -ne 0) {
            throw "Could not copy $name from the VPS."
        }
        $actualHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "Checksum mismatch for $name."
        }
        Move-Item -LiteralPath $temporary -Destination $localPath -Force
        Write-Output "Copied and verified $name"
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}
