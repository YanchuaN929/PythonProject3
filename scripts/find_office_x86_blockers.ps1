[CmdletBinding()]
param(
    [switch]$ScanOnly,
    [string]$OutputDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $OutputDir = $PSScriptRoot
    }
    else {
        $OutputDir = (Get-Location).Path
    }
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-OptionalString {
    param(
        [object]$InputObject,
        [string]$PropertyName
    )

    if ($null -eq $InputObject) {
        return ""
    }

    $property = $InputObject.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) {
        return ""
    }

    return [string]$property.Value
}

function Get-OptionalValue {
    param(
        [object]$InputObject,
        [string]$PropertyName
    )

    if ($null -eq $InputObject) {
        return $null
    }

    $property = $InputObject.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-RegistryValueString {
    param(
        [string]$Path,
        [string]$ValueName = ""
    )

    if (-not (Test-NonEmptyPathExists -Path $Path)) {
        return ""
    }

    try {
        $item = Get-Item -Path $Path -ErrorAction Stop
        $value = $item.GetValue($ValueName, "")
        if ($null -eq $value) {
            return ""
        }
        return [string]$value
    }
    catch {
        return ""
    }
}

function Test-NonEmptyPathExists {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    return (Test-Path -LiteralPath $Path)
}

function Test-IsOfficeCandidate {
    param(
        [string]$Name,
        [string]$Publisher,
        [string]$InstallLocation,
        [string]$Command
    )

    $combined = @($Name, $Publisher, $InstallLocation, $Command) -join " | "
    if ([string]::IsNullOrWhiteSpace($combined)) {
        return $false
    }

    if ($combined -match '(?i)visual studio tools for office runtime|webview2|office telemetry|office viewer component|open xml sdk|office developer tools|developer tools for office|wps office|libreoffice|openoffice|kingsoft office') {
        return $false
    }

    if ($combined -match '(?i)microsoft 365|click[- ]?to[- ]?run|visio|project|access database engine|proofing tools|language pack|skype for business|sharepoint designer|officeclicktorun') {
        return $true
    }

    if ($Name -match '(?i)\boffice\b') {
        if ($Publisher -match '(?i)microsoft' -or $InstallLocation -match '(?i)microsoft office|clicktorun|office1[4569]' -or $Command -match '(?i)microsoft office|clicktorun|office1[4569]') {
            return $true
        }
    }

    if ($InstallLocation -match '(?i)program files \(x86\).*(microsoft office|clicktorun)' -or $Command -match '(?i)program files \(x86\).*(microsoft office|clicktorun)') {
        return $true
    }

    return $false
}

function Get-Bitness {
    param(
        [string]$RegistryPath,
        [string]$Name,
        [string]$InstallLocation,
        [string]$Command,
        [string]$PathText
    )

    $combined = @($RegistryPath, $Name, $InstallLocation, $Command, $PathText) -join " | "
    if ($combined -match '(?i)wow6432node|program files \(x86\)|\\x86\\|\b32-bit\b|\bx86\b') {
        return "32-bit"
    }

    if ($combined -match '(?i)\b64-bit\b|\bx64\b') {
        return "64-bit"
    }

    if ($combined -match '(?i)\\program files\\') {
        return "64-bit/unknown"
    }

    return "Unknown"
}

function Convert-ToNativeRegistryPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    $normalized = $Path -replace '^Microsoft\.PowerShell\.Core\\Registry::', 'Registry::'
    if ($normalized -match '^Registry::HKEY_LOCAL_MACHINE\\') {
        return $normalized -replace '^Registry::HKEY_LOCAL_MACHINE\\', 'HKEY_LOCAL_MACHINE\'
    }
    if ($normalized -match '^Registry::HKEY_CURRENT_USER\\') {
        return $normalized -replace '^Registry::HKEY_CURRENT_USER\\', 'HKEY_CURRENT_USER\'
    }
    if ($normalized -match '^HKLM:\\') {
        return $normalized -replace '^HKLM:\\', 'HKEY_LOCAL_MACHINE\'
    }
    if ($normalized -match '^HKCU:\\') {
        return $normalized -replace '^HKCU:\\', 'HKEY_CURRENT_USER\'
    }

    return $null
}

function Backup-RegistryKey {
    param(
        [string]$RegistryPath,
        [string]$BackupDir
    )

    $nativePath = Convert-ToNativeRegistryPath -Path $RegistryPath
    if (-not $nativePath) {
        return
    }

    $safeName = ($nativePath -replace '[\\/:*?"<>|]', '_')
    $backupFile = Join-Path $BackupDir ($safeName + ".reg")
    & reg.exe export $nativePath $backupFile /y | Out-Null
}

function New-Finding {
    param(
        [string]$Category,
        [string]$Name,
        [string]$Bitness,
        [string]$Reason,
        [string]$Source,
        [string]$InstallLocation,
        [string]$Command,
        [string]$CleanupKind,
        [string]$CleanupTarget,
        [string]$ForceCleanupKind,
        [string]$ForceCleanupTarget,
        [bool]$Hidden = $false
    )

    [PSCustomObject]@{
        Category           = $Category
        Name               = $Name
        Bitness            = $Bitness
        Reason             = $Reason
        Source             = $Source
        InstallLocation    = $InstallLocation
        Command            = $Command
        Hidden             = $Hidden
        CleanupKind        = $CleanupKind
        CleanupTarget      = $CleanupTarget
        ForceCleanupKind   = $ForceCleanupKind
        ForceCleanupTarget = $ForceCleanupTarget
    }
}

function Get-UninstallRegistryFindings {
    $results = @()
    $roots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )

    foreach ($root in $roots) {
        $items = Get-ItemProperty -Path $root -ErrorAction SilentlyContinue
        foreach ($item in $items) {
            $displayName = Get-OptionalString -InputObject $item -PropertyName 'DisplayName'
            if ([string]::IsNullOrWhiteSpace($displayName)) {
                $displayName = Get-OptionalString -InputObject $item -PropertyName 'ProductName'
            }
            if ([string]::IsNullOrWhiteSpace($displayName)) {
                continue
            }

            $publisher = Get-OptionalString -InputObject $item -PropertyName 'Publisher'
            $installLocation = Get-OptionalString -InputObject $item -PropertyName 'InstallLocation'
            $quietCommand = Get-OptionalString -InputObject $item -PropertyName 'QuietUninstallString'
            $uninstallCommand = Get-OptionalString -InputObject $item -PropertyName 'UninstallString'
            $effectiveCommand = if ($quietCommand) { $quietCommand } else { $uninstallCommand }

            if (-not (Test-IsOfficeCandidate -Name $displayName -Publisher $publisher -InstallLocation $installLocation -Command $effectiveCommand)) {
                continue
            }

            $registryPath = [string]$item.PSPath
            $bitness = Get-Bitness -RegistryPath $registryPath -Name $displayName -InstallLocation $installLocation -Command $effectiveCommand -PathText ""
            if ($bitness -ne "32-bit") {
                continue
            }

            $hidden = $false
            $systemComponent = Get-OptionalValue -InputObject $item -PropertyName 'SystemComponent'
            if ($null -ne $systemComponent) {
                $hidden = [bool]($systemComponent -eq 1)
            }

            $results += New-Finding `
                -Category "UninstallEntry" `
                -Name $displayName `
                -Bitness $bitness `
                -Reason ($(if ($hidden) { "Hidden uninstall entry for 32-bit Office family component" } else { "Visible uninstall entry for 32-bit Office family component" })) `
                -Source $registryPath `
                -InstallLocation $installLocation `
                -Command $effectiveCommand `
                -CleanupKind ($(if ($effectiveCommand) { "Command" } else { "Registry" })) `
                -CleanupTarget ($(if ($effectiveCommand) { $effectiveCommand } else { $registryPath })) `
                -ForceCleanupKind "Registry" `
                -ForceCleanupTarget $registryPath `
                -Hidden $hidden
        }
    }

    return $results
}

function Get-OfficeStorePackageFindings {
    $results = @()

    $packages = @()
    try {
        if (Test-IsAdministrator) {
            $packages = @(Get-AppxPackage -AllUsers -ErrorAction Stop |
                Where-Object { $_.Name -like 'Microsoft.Office.Desktop*' })
        }
        else {
            $packages = @(Get-AppxPackage -ErrorAction Stop |
                Where-Object { $_.Name -like 'Microsoft.Office.Desktop*' })
        }
    }
    catch {
        $packages = @()
    }

    foreach ($package in $packages) {
        $arch = [string]$package.Architecture
        $installLocation = [string]$package.InstallLocation
        $bitness = if ($arch -match '(?i)x86') { '32-bit' } elseif ($arch -match '(?i)x64') { '64-bit' } else { 'Unknown' }

        $results += New-Finding `
            -Category "StorePackage" `
            -Name $package.Name `
            -Bitness $bitness `
            -Reason "Microsoft Store Office package is installed and may block desktop Office setup" `
            -Source $package.PackageFullName `
            -InstallLocation $installLocation `
            -Command "" `
            -CleanupKind "AppxPackage" `
            -CleanupTarget $package.PackageFullName `
            -ForceCleanupKind "" `
            -ForceCleanupTarget ""
    }

    $provisioned = @()
    if (Test-IsAdministrator) {
        try {
            $provisioned = @(Get-AppxProvisionedPackage -Online -ErrorAction Stop |
                Where-Object { $_.DisplayName -like 'Microsoft.Office.Desktop*' })
        }
        catch {
            $provisioned = @()
        }
    }

    foreach ($package in $provisioned) {
        $results += New-Finding `
            -Category "ProvisionedPackage" `
            -Name $package.DisplayName `
            -Bitness "Unknown" `
            -Reason "Provisioned Microsoft Store Office package may reinstall or keep setup blocked" `
            -Source $package.PackageName `
            -InstallLocation "" `
            -Command "" `
            -CleanupKind "ProvisionedPackage" `
            -CleanupTarget $package.PackageName `
            -ForceCleanupKind "" `
            -ForceCleanupTarget ""
    }

    return $results
}

function Get-InstallerDatabaseFindings {
    $results = @()
    $userDataRoot = 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData'
    $sidKeys = Get-ChildItem -Path $userDataRoot -ErrorAction SilentlyContinue

    foreach ($sidKey in $sidKeys) {
        $productsPath = Join-Path $sidKey.PSPath 'Products'
        if ([string]::IsNullOrWhiteSpace($productsPath)) {
            continue
        }
        $productKeys = Get-ChildItem -Path $productsPath -ErrorAction SilentlyContinue
        foreach ($productKey in $productKeys) {
            $installPropsPath = Join-Path $productKey.PSPath 'InstallProperties'
            if (-not (Test-NonEmptyPathExists -Path $installPropsPath)) {
                continue
            }

            $props = Get-ItemProperty -Path $installPropsPath -ErrorAction SilentlyContinue
            if (-not $props) {
                continue
            }

            $displayName = Get-OptionalString -InputObject $props -PropertyName 'DisplayName'
            if ([string]::IsNullOrWhiteSpace($displayName)) {
                continue
            }

            $installLocation = Get-OptionalString -InputObject $props -PropertyName 'InstallLocation'
            $uninstallCommand = Get-OptionalString -InputObject $props -PropertyName 'UninstallString'
            $publisher = Get-OptionalString -InputObject $props -PropertyName 'Publisher'
            if (-not (Test-IsOfficeCandidate -Name $displayName -Publisher $publisher -InstallLocation $installLocation -Command $uninstallCommand)) {
                continue
            }

            $bitness = Get-Bitness -RegistryPath $installPropsPath -Name $displayName -InstallLocation $installLocation -Command $uninstallCommand -PathText ""
            if ($bitness -ne "32-bit") {
                continue
            }

            $results += New-Finding `
                -Category "InstallerCache" `
                -Name $displayName `
                -Bitness $bitness `
                -Reason "Windows Installer cache still contains a 32-bit Office family component" `
                -Source $installPropsPath `
                -InstallLocation $installLocation `
                -Command $uninstallCommand `
                -CleanupKind ($(if ($uninstallCommand) { "Command" } else { "Registry" })) `
                -CleanupTarget ($(if ($uninstallCommand) { $uninstallCommand } else { $installPropsPath })) `
                -ForceCleanupKind "Registry" `
                -ForceCleanupTarget $installPropsPath
        }
    }

    return $results
}

function Get-OfficeVersionRegistryFindings {
    $results = @()
    $versions = @('14.0', '15.0', '16.0')
    $versionKeyRoots = @(
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\{0}',
        'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Office\{0}',
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\WOW6432Node\Microsoft\Office\{0}'
    )

    foreach ($version in $versions) {
        foreach ($template in $versionKeyRoots) {
            $path = $template -f $version
            if (-not (Test-NonEmptyPathExists -Path $path)) {
                continue
            }

            $results += New-Finding `
                -Category "VersionRegistry" `
                -Name ("Office {0} registry root" -f $version) `
                -Bitness "32-bit" `
                -Reason "32-bit Office version registry root still exists under WOW6432Node" `
                -Source $path `
                -InstallLocation "" `
                -Command "" `
                -CleanupKind "" `
                -CleanupTarget "" `
                -ForceCleanupKind "Registry" `
                -ForceCleanupTarget $path
        }
    }

    return $results
}

function Get-OfficeInstallRootFindings {
    $results = @()
    $versions = @('14.0', '15.0', '16.0')
    $subkeys = @('Common\InstallRoot', 'Word\InstallRoot', 'Excel\InstallRoot', 'PowerPoint\InstallRoot', 'Outlook\InstallRoot', 'Access\InstallRoot')
    $roots = @(
        'HKLM:\SOFTWARE\Microsoft\Office\{0}\{1}',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\{0}\{1}',
        'HKCU:\SOFTWARE\Microsoft\Office\{0}\{1}',
        'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Office\{0}\{1}',
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\Microsoft\Office\{0}\{1}',
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\WOW6432Node\Microsoft\Office\{0}\{1}'
    )

    foreach ($version in $versions) {
        foreach ($subkey in $subkeys) {
            foreach ($template in $roots) {
                $path = $template -f $version, $subkey
                if (-not (Test-NonEmptyPathExists -Path $path)) {
                    continue
                }

                $installPath = Get-RegistryValueString -Path $path -ValueName 'Path'
                $defaultValue = Get-RegistryValueString -Path $path -ValueName ''
                $bitness = Get-Bitness -RegistryPath $path -Name ("Office {0}" -f $version) -InstallLocation $installPath -Command $defaultValue -PathText ""
                if ($bitness -ne '32-bit') {
                    continue
                }

                $results += New-Finding `
                    -Category "InstallRoot" `
                    -Name ("Office {0} {1}" -f $version, $subkey) `
                    -Bitness $bitness `
                    -Reason "Office install root points to a 32-bit path" `
                    -Source $path `
                    -InstallLocation $installPath `
                    -Command $defaultValue `
                    -CleanupKind "" `
                    -CleanupTarget "" `
                    -ForceCleanupKind "Registry" `
                    -ForceCleanupTarget $path
            }
        }
    }

    return $results
}

function Get-OfficeAppPathFindings {
    $results = @()
    $executables = @('WINWORD.EXE', 'EXCEL.EXE', 'POWERPNT.EXE', 'OUTLOOK.EXE', 'MSACCESS.EXE', 'VISIO.EXE', 'MSPUB.EXE')
    $roots = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{0}',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{0}',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{0}',
        'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{0}',
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\Microsoft\Windows\CurrentVersion\App Paths\{0}',
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{0}'
    )

    foreach ($exe in $executables) {
        foreach ($template in $roots) {
            $path = $template -f $exe
            if (-not (Test-NonEmptyPathExists -Path $path)) {
                continue
            }

            $defaultValue = Get-RegistryValueString -Path $path -ValueName ''
            $pathValue = Get-RegistryValueString -Path $path -ValueName 'Path'
            $bitness = Get-Bitness -RegistryPath $path -Name $exe -InstallLocation $pathValue -Command $defaultValue -PathText ""
            if ($bitness -ne '32-bit') {
                continue
            }

            $results += New-Finding `
                -Category "AppPath" `
                -Name $exe `
                -Bitness $bitness `
                -Reason "Office executable app path still points to a 32-bit install" `
                -Source $path `
                -InstallLocation $pathValue `
                -Command $defaultValue `
                -CleanupKind "" `
                -CleanupTarget "" `
                -ForceCleanupKind "Registry" `
                -ForceCleanupTarget $path
        }
    }

    return $results
}

function Get-ClickToRunFindings {
    $results = @()
    $paths = @(
        'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\ClickToRun\Configuration'
    )

    foreach ($path in $paths) {
        if (-not (Test-NonEmptyPathExists -Path $path)) {
            continue
        }

        $item = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue
        if (-not $item) {
            continue
        }

        $platform = Get-OptionalString -InputObject $item -PropertyName 'Platform'
        $clientFolder = Get-OptionalString -InputObject $item -PropertyName 'ClientFolder'
        $installationPath = Get-OptionalString -InputObject $item -PropertyName 'InstallPath'
        if ([string]::IsNullOrWhiteSpace($installationPath)) {
            $installationPath = Get-OptionalString -InputObject $item -PropertyName 'InstallationPath'
        }

        $productIds = Get-OptionalString -InputObject $item -PropertyName 'ProductReleaseIds'
        $bitness = Get-Bitness -RegistryPath $path -Name $productIds -InstallLocation $installationPath -Command "" -PathText ($platform + " " + $clientFolder)
        if ($bitness -ne "32-bit") {
            continue
        }

        $results += New-Finding `
            -Category "ClickToRunConfig" `
            -Name ($(if ($productIds) { $productIds } else { "Office Click-to-Run configuration" })) `
            -Bitness $bitness `
            -Reason "Click-to-Run configuration still points to a 32-bit Office platform" `
            -Source $path `
            -InstallLocation $installationPath `
            -Command "" `
            -CleanupKind "" `
            -CleanupTarget "" `
            -ForceCleanupKind "Registry" `
            -ForceCleanupTarget $path
    }

    return $results
}

function Get-OfficeProcessFindings {
    $results = @()
    $processes = Get-CimInstance -ClassName Win32_Process -ErrorAction SilentlyContinue

    foreach ($process in $processes) {
        $name = [string]$process.Name
        $path = [string]$process.ExecutablePath
        $candidate = Test-IsOfficeCandidate -Name $name -Publisher "" -InstallLocation $path -Command $path
        if (-not $candidate -and $name -notmatch '(?i)^officeclicktorun\.exe$|^winword\.exe$|^excel\.exe$|^powerpnt\.exe$|^outlook\.exe$|^msaccess\.exe$|^visio\.exe$|^mspub\.exe$') {
            continue
        }

        $bitness = Get-Bitness -RegistryPath "" -Name $name -InstallLocation $path -Command "" -PathText ""
        if ($bitness -ne "32-bit") {
            continue
        }

        $results += New-Finding `
            -Category "Process" `
            -Name ("{0} (PID {1})" -f $name, $process.ProcessId) `
            -Bitness $bitness `
            -Reason "32-bit Office related process is still running" `
            -Source $path `
            -InstallLocation $path `
            -Command "" `
            -CleanupKind "Process" `
            -CleanupTarget ([string]$process.ProcessId) `
            -ForceCleanupKind "" `
            -ForceCleanupTarget ""
    }

    return $results
}

function Get-OfficeServiceFindings {
    $results = @()
    $services = Get-CimInstance -ClassName Win32_Service -ErrorAction SilentlyContinue

    foreach ($service in $services) {
        $name = [string]$service.Name
        $displayName = [string]$service.DisplayName
        $pathName = [string]$service.PathName
        $candidate = $false
        if ($name -match '(?i)^clicktorunsvc$|^officesvc$|^osppsvc$|^ose$') {
            $candidate = $true
        }
        elseif ($displayName -match '(?i)microsoft office|office click[- ]?to[- ]?run|office software protection platform') {
            $candidate = $true
        }
        elseif ($pathName -match '(?i)microsoft office|office1[4569]|clicktorun|officesoftwareprotectionplatform') {
            $candidate = $true
        }

        if (-not $candidate) {
            continue
        }

        $bitness = Get-Bitness -RegistryPath "" -Name ($name + " " + $displayName) -InstallLocation $pathName -Command "" -PathText ""
        if ($bitness -ne "32-bit") {
            continue
        }

        $serviceRegistryPath = "HKLM:\SYSTEM\CurrentControlSet\Services\$name"
        $results += New-Finding `
            -Category "Service" `
            -Name ("{0} ({1})" -f $displayName, $name) `
            -Bitness $bitness `
            -Reason "32-bit Office related service is still registered" `
            -Source $pathName `
            -InstallLocation $pathName `
            -Command "" `
            -CleanupKind "Service" `
            -CleanupTarget $name `
            -ForceCleanupKind "ServiceDelete" `
            -ForceCleanupTarget $name
    }

    return $results
}

function Get-OfficeFolderFindings {
    $results = @()
    $x86ProgramFiles = ${env:ProgramFiles(x86)}
    if ([string]::IsNullOrWhiteSpace($x86ProgramFiles)) {
        return $results
    }

    $paths = @(
        (Join-Path $x86ProgramFiles 'Microsoft Office'),
        (Join-Path $x86ProgramFiles 'Microsoft Office\root'),
        (Join-Path $x86ProgramFiles 'Microsoft Office\root\Office16'),
        (Join-Path $x86ProgramFiles 'Common Files\Microsoft Shared\ClickToRun'),
        (Join-Path $x86ProgramFiles 'Common Files\Microsoft Shared\Office16'),
        (Join-Path $x86ProgramFiles 'Common Files\Microsoft Shared\OFFICE16')
    )

    foreach ($path in $paths | Select-Object -Unique) {
        if (-not (Test-NonEmptyPathExists -Path $path)) {
            continue
        }

        $results += New-Finding `
            -Category "Folder" `
            -Name ([IO.Path]::GetFileName($path)) `
            -Bitness "32-bit" `
            -Reason "32-bit Office installation folder still exists" `
            -Source $path `
            -InstallLocation $path `
            -Command "" `
            -CleanupKind "" `
            -CleanupTarget "" `
            -ForceCleanupKind "Folder" `
            -ForceCleanupTarget $path
    }

    return $results
}

function Deduplicate-Findings {
    param([object[]]$Items)

    $seen = @{}
    $results = @()
    foreach ($item in $Items) {
        $key = @(
            $item.Category,
            $item.Name,
            $item.Bitness,
            $item.Source,
            $item.InstallLocation,
            $item.Command
        ) -join '|'

        if ($seen.ContainsKey($key)) {
            continue
        }

        $seen[$key] = $true
        $results += $item
    }

    return $results
}

function Get-AllFindings {
    $all = @()
    $all += Get-OfficeStorePackageFindings
    $all += Get-UninstallRegistryFindings
    $all += Get-InstallerDatabaseFindings
    $all += Get-OfficeVersionRegistryFindings
    $all += Get-OfficeInstallRootFindings
    $all += Get-OfficeAppPathFindings
    $all += Get-ClickToRunFindings
    $all += Get-OfficeProcessFindings
    $all += Get-OfficeServiceFindings
    $all += Get-OfficeFolderFindings
    return Deduplicate-Findings -Items $all
}

function Write-FindingsSummary {
    param([object[]]$Findings)

    if (-not $Findings -or $Findings.Count -eq 0) {
        Write-Host ""
        Write-Host "No obvious 32-bit Office blockers were found." -ForegroundColor Green
        return
    }

    Write-Host ""
    Write-Host "Possible blockers:" -ForegroundColor Yellow
    $Findings |
        Sort-Object Category, Name |
        Select-Object Category, Name, Bitness, Reason |
        Format-Table -AutoSize | Out-Host
}

function Save-Reports {
    param(
        [object[]]$Findings,
        [string]$Directory
    )

    if (-not (Test-NonEmptyPathExists -Path $Directory)) {
        New-Item -Path $Directory -ItemType Directory | Out-Null
    }

    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $jsonPath = Join-Path $Directory ("office_x86_blockers_{0}.json" -f $timestamp)
    $txtPath = Join-Path $Directory ("office_x86_blockers_{0}.txt" -f $timestamp)

    $Findings | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add(("Scan time: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')))
    $lines.Add(("Admin: {0}" -f (Test-IsAdministrator)))
    $lines.Add(("Items: {0}" -f $Findings.Count))
    $lines.Add("")

    $index = 1
    foreach ($item in ($Findings | Sort-Object Category, Name)) {
        $lines.Add(("[{0}] {1}" -f $index, $item.Category))
        $lines.Add(("Name: {0}" -f $item.Name))
        $lines.Add(("Bitness: {0}" -f $item.Bitness))
        $lines.Add(("Reason: {0}" -f $item.Reason))
        $lines.Add(("Source: {0}" -f $item.Source))
        if ($item.InstallLocation) {
            $lines.Add(("InstallLocation: {0}" -f $item.InstallLocation))
        }
        if ($item.Command) {
            $lines.Add(("Command: {0}" -f $item.Command))
        }
        $lines.Add(("Hidden: {0}" -f $item.Hidden))
        $lines.Add("")
        $index++
    }

    $lines | Set-Content -Path $txtPath -Encoding UTF8

    return [PSCustomObject]@{
        JsonPath = $jsonPath
        TextPath = $txtPath
    }
}

function Invoke-UninstallCommand {
    param([string]$Command)

    if ([string]::IsNullOrWhiteSpace($Command)) {
        return
    }

    $trimmed = $Command.Trim()
    if ($trimmed -match '(?i)^"?.*msiexec(?:\.exe)?"?\s+(.*)$') {
        $args = $Matches[1]
        if ($args -match '(?i)/i\s*\{') {
            $args = $args -replace '(?i)/i', '/x'
        }
        if ($args -notmatch '(?i)(/quiet|/qn|/passive)') {
            $args = $args + ' /passive /norestart'
        }
        Start-Process -FilePath 'msiexec.exe' -ArgumentList $args -Wait -NoNewWindow
        return
    }

    Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', $trimmed) -Wait -NoNewWindow
}

function Invoke-NormalCleanup {
    param([object[]]$Findings)

    foreach ($item in $Findings) {
        switch ($item.CleanupKind) {
            "Process" {
                Write-Host ("Stopping process {0}" -f $item.Name) -ForegroundColor Cyan
                Stop-Process -Id ([int]$item.CleanupTarget) -Force -ErrorAction SilentlyContinue
            }
            "Service" {
                Write-Host ("Stopping service {0}" -f $item.CleanupTarget) -ForegroundColor Cyan
                Stop-Service -Name $item.CleanupTarget -Force -ErrorAction SilentlyContinue
            }
            "Command" {
                Write-Host ("Running uninstall command for {0}" -f $item.Name) -ForegroundColor Cyan
                Invoke-UninstallCommand -Command $item.CleanupTarget
            }
            "AppxPackage" {
                Write-Host ("Removing Appx package {0}" -f $item.Name) -ForegroundColor Cyan
                Remove-AppxPackage -Package $item.CleanupTarget -AllUsers -ErrorAction SilentlyContinue
            }
            "ProvisionedPackage" {
                Write-Host ("Removing provisioned package {0}" -f $item.Name) -ForegroundColor Cyan
                Remove-AppxProvisionedPackage -Online -PackageName $item.CleanupTarget -ErrorAction SilentlyContinue | Out-Null
            }
            default {
            }
        }
    }
}

function Invoke-ForceCleanup {
    param(
        [object[]]$Findings,
        [string]$BackupDir
    )

    foreach ($item in $Findings) {
        switch ($item.ForceCleanupKind) {
            "Folder" {
                if (Test-NonEmptyPathExists -Path $item.ForceCleanupTarget) {
                    Write-Host ("Removing folder {0}" -f $item.ForceCleanupTarget) -ForegroundColor Magenta
                    Remove-Item -LiteralPath $item.ForceCleanupTarget -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            "Registry" {
                if (Test-NonEmptyPathExists -Path $item.ForceCleanupTarget) {
                    Write-Host ("Removing registry key {0}" -f $item.ForceCleanupTarget) -ForegroundColor Magenta
                    Backup-RegistryKey -RegistryPath $item.ForceCleanupTarget -BackupDir $BackupDir
                    Remove-Item -Path $item.ForceCleanupTarget -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            "ServiceDelete" {
                Write-Host ("Deleting service {0}" -f $item.ForceCleanupTarget) -ForegroundColor Magenta
                $serviceKey = "HKLM:\SYSTEM\CurrentControlSet\Services\{0}" -f $item.ForceCleanupTarget
                if (Test-NonEmptyPathExists -Path $serviceKey) {
                    Backup-RegistryKey -RegistryPath $serviceKey -BackupDir $BackupDir
                }
                & sc.exe delete $item.ForceCleanupTarget | Out-Null
            }
            default {
            }
        }
    }
}

$isAdmin = Test-IsAdministrator
if (-not $isAdmin) {
    Write-Warning "Run this script in an elevated PowerShell window if you want it to remove registry keys, services, or Office files."
}

Write-Host "Scanning this PC for 32-bit Office blockers..." -ForegroundColor White
$findings = @(Get-AllFindings)
$reportPaths = Save-Reports -Findings $findings -Directory $OutputDir
Write-FindingsSummary -Findings $findings

Write-Host ""
Write-Host ("Text report: {0}" -f $reportPaths.TextPath) -ForegroundColor Gray
Write-Host ("JSON report: {0}" -f $reportPaths.JsonPath) -ForegroundColor Gray

if ($findings.Count -eq 0 -or $ScanOnly) {
    return
}

Start-Process -FilePath 'notepad.exe' -ArgumentList $reportPaths.TextPath -ErrorAction SilentlyContinue

Write-Host ""
$reviewInput = Read-Host "Review the report first. Press Enter to continue, or type Q to quit"
if ($reviewInput -match '^(?i)q$') {
    Write-Host "Cancelled before cleanup." -ForegroundColor Yellow
    return
}

$deleteInput = Read-Host "Type DELETE to start normal cleanup (stop services/processes and run uninstall commands)"
if ($deleteInput -cne 'DELETE') {
    Write-Host "Cleanup cancelled." -ForegroundColor Yellow
    return
}

Invoke-NormalCleanup -Findings $findings

$forceCandidates = @($findings | Where-Object { $_.ForceCleanupKind })
if ($forceCandidates.Count -gt 0) {
    Write-Host ""
    Write-Host "Residual items that can be force-removed:" -ForegroundColor Yellow
    $forceCandidates |
        Select-Object Category, Name, ForceCleanupKind, ForceCleanupTarget |
        Format-Table -AutoSize | Out-Host

    $forceInput = Read-Host "Type FORCE to remove leftover folders/registry keys/services, or press Enter to skip"
    if ($forceInput -ceq 'FORCE') {
        $backupDir = Join-Path $OutputDir ("office_x86_backups_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
        if (-not (Test-NonEmptyPathExists -Path $backupDir)) {
            New-Item -Path $backupDir -ItemType Directory | Out-Null
        }
        Invoke-ForceCleanup -Findings $forceCandidates -BackupDir $backupDir
        Write-Host ("Registry backups (if any) were saved to: {0}" -f $backupDir) -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Scan and cleanup flow finished. Reboot the PC before rerunning Office setup." -ForegroundColor Green
