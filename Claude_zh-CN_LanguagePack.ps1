param(
    [string]$Action = "install"
)

$ErrorActionPreference = "Stop"

function Find-ClaudePath {
    $packages = Get-AppxPackage -Name "Claude" -ErrorAction SilentlyContinue

    if ($packages) {
        $package = $packages | Select-Object -First 1
        $installPath = $package.InstallLocation

        if ($installPath -and (Test-Path $installPath)) {
            return $installPath
        }
    }

    $fallback = Get-ChildItem "C:\Program Files\WindowsApps\Claude_*" -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($fallback) {
        return $fallback.FullName
    }

    return $null
}

function Grant-WriteAccess {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    try {
        $acl = Get-Acl $Path
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $identity,
            "FullControl",
            "ContainerInherit,ObjectInherit",
            "None",
            "Allow"
        )

        $acl.SetAccessRule($rule)
        Set-Acl $Path $acl -ErrorAction SilentlyContinue
    }
    catch {
        Write-Host "  [警告] 无法设置权限: $Path" -ForegroundColor DarkYellow
        Write-Host "  $_" -ForegroundColor DarkYellow
    }
}

function Replace-BytesInFile {
    param(
        [string]$FilePath,
        [byte[]]$OldPattern,
        [byte[]]$NewPattern
    )

    if (-not (Test-Path $FilePath)) {
        return $false
    }

    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $pos = -1

    for ($i = 0; $i -le $bytes.Length - $OldPattern.Length; $i++) {
        $match = $true

        for ($j = 0; $j -lt $OldPattern.Length; $j++) {
            if ($bytes[$i + $j] -ne $OldPattern[$j]) {
                $match = $false
                break
            }
        }

        if ($match) {
            $pos = $i
            break
        }
    }

    if ($pos -lt 0) {
        return $false
    }

    $newBytes = New-Object byte[] ($bytes.Length + $NewPattern.Length - $OldPattern.Length)

    [Array]::Copy($bytes, 0, $newBytes, 0, $pos)
    [Array]::Copy($NewPattern, 0, $newBytes, $pos, $NewPattern.Length)
    [Array]::Copy(
        $bytes,
        $pos + $OldPattern.Length,
        $newBytes,
        $pos + $NewPattern.Length,
        $bytes.Length - $pos - $OldPattern.Length
    )

    [System.IO.File]::WriteAllBytes($FilePath, $newBytes)

    return $true
}

function Get-ScriptDirectory {
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName

    if (-not $scriptDir) {
        $scriptDir = $PSScriptRoot
    }

    if (-not $scriptDir) {
        $scriptDir = Get-Location
    }

    return $scriptDir
}

function Get-ClaudeResourcesPath {
    $claudePath = Find-ClaudePath

    if (-not $claudePath) {
        Write-Host "[错误] 未找到 Claude Desktop 安装" -ForegroundColor Red
        return $null
    }

    Write-Host "  找到 Claude Desktop: $claudePath" -ForegroundColor Green

    $resourcesPath = "$claudePath\app\resources"

    if (-not (Test-Path $resourcesPath)) {
        Write-Host "[错误] 未找到 resources 目录: $resourcesPath" -ForegroundColor Red
        return $null
    }

    return $resourcesPath
}

function Export-EnglishText {
    Write-Host "=== Claude Desktop 英文文本提取 ===" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "[1/3] 查找 Claude Desktop 安装路径..." -ForegroundColor Yellow
    $resourcesPath = Get-ClaudeResourcesPath

    if (-not $resourcesPath) {
        return
    }

    $scriptDir = Get-ScriptDirectory

    $englishOutDir = "$scriptDir\extracted-en-US"
    $templateOutDir = "$scriptDir\translation-template"

    New-Item -ItemType Directory -Force -Path "$englishOutDir\ion-dist" | Out-Null
    New-Item -ItemType Directory -Force -Path "$englishOutDir\desktop-shell" | Out-Null
    New-Item -ItemType Directory -Force -Path "$englishOutDir\statsig" | Out-Null

    New-Item -ItemType Directory -Force -Path "$templateOutDir\ion-dist" | Out-Null
    New-Item -ItemType Directory -Force -Path "$templateOutDir\desktop-shell" | Out-Null
    New-Item -ItemType Directory -Force -Path "$templateOutDir\statsig" | Out-Null

    $targets = @(
        @{
            Name = "ion-dist"
            Source = "$resourcesPath\ion-dist\i18n\en-US.json"
            EnglishOutput = "$englishOutDir\ion-dist\en-US.json"
            TemplateOutput = "$templateOutDir\ion-dist\zh-CN.json"
        },
        @{
            Name = "desktop-shell"
            Source = "$resourcesPath\en-US.json"
            EnglishOutput = "$englishOutDir\desktop-shell\en-US.json"
            TemplateOutput = "$templateOutDir\desktop-shell\zh-CN.json"
        },
        @{
            Name = "statsig"
            Source = "$resourcesPath\ion-dist\i18n\statsig\en-US.json"
            EnglishOutput = "$englishOutDir\statsig\en-US.json"
            TemplateOutput = "$templateOutDir\statsig\zh-CN.json"
        }
    )

    Write-Host "[2/3] 提取 en-US 原文并生成 zh-CN 翻译模板..." -ForegroundColor Yellow

    foreach ($target in $targets) {
        Write-Host "  处理: $($target.Name)" -ForegroundColor White

        if (Test-Path $target.Source) {
            Copy-Item $target.Source $target.EnglishOutput -Force
            Copy-Item $target.Source $target.TemplateOutput -Force

            Write-Host "    英文原文: $($target.EnglishOutput)" -ForegroundColor Green
            Write-Host "    翻译模板: $($target.TemplateOutput)" -ForegroundColor Green
        }
        else {
            Write-Host "    [警告] 未找到英文文件: $($target.Source)" -ForegroundColor DarkYellow
        }
    }

    Write-Host "[3/3] 提取完成" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "=== 英文文本提取完成 ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "英文原文目录:" -ForegroundColor Cyan
    Write-Host "  $englishOutDir" -ForegroundColor White
    Write-Host ""
    Write-Host "待翻译模板目录:" -ForegroundColor Cyan
    Write-Host "  $templateOutDir" -ForegroundColor White
    Write-Host ""
    Write-Host "翻译说明:" -ForegroundColor Cyan
    Write-Host "  1. 翻译 translation-template 目录中的 zh-CN.json" -ForegroundColor White
    Write-Host "  2. 只修改 JSON 的 value，不要修改 key" -ForegroundColor White
    Write-Host "  3. 不要删除 {count}、{name}、%s、<b>...</b> 等占位符" -ForegroundColor White
    Write-Host "  4. 翻译完成后，把 translation-template 中的 3 个目录复制回脚本同级目录" -ForegroundColor White
    Write-Host "  5. 然后运行: .\Claude_zh-CN_LanguagePack.ps1 install" -ForegroundColor White
    Write-Host ""
}

function Install-LanguagePack {
    Write-Host "=== Claude Desktop 中文语言包安装 ===" -ForegroundColor Cyan
    Write-Host ""

    $scriptDir = Get-ScriptDirectory
    $packDir = $scriptDir

    $requiredFiles = @(
        "$packDir\ion-dist\zh-CN.json",
        "$packDir\desktop-shell\zh-CN.json",
        "$packDir\statsig\zh-CN.json"
    )

    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-Host "[错误] 缺少语言文件: $file" -ForegroundColor Red
            Write-Host "请确保语言包文件完整，或者先运行 extract 提取模板后再翻译。" -ForegroundColor Red
            return
        }
    }

    Write-Host "[1/6] 查找 Claude Desktop 安装路径..." -ForegroundColor Yellow
    $resourcesPath = Get-ClaudeResourcesPath

    if (-not $resourcesPath) {
        return
    }

    Write-Host "[2/6] 获取写入权限..." -ForegroundColor Yellow

    try {
        $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator
        )

        if (-not $admin) {
            Write-Host "  [警告] 当前未以管理员权限运行，某些操作可能失败" -ForegroundColor DarkYellow
        }

        Grant-WriteAccess -Path $resourcesPath
        Grant-WriteAccess -Path "$resourcesPath\ion-dist"
        Grant-WriteAccess -Path "$resourcesPath\ion-dist\i18n"
        Grant-WriteAccess -Path "$resourcesPath\ion-dist\i18n\statsig"
        Grant-WriteAccess -Path "$resourcesPath\ion-dist\assets"
        Grant-WriteAccess -Path "$resourcesPath\ion-dist\assets\v1"

        Write-Host "  权限处理完成" -ForegroundColor Green
    }
    catch {
        Write-Host "  [警告] 权限设置部分失败: $_" -ForegroundColor DarkYellow
    }

    Write-Host "[3/6] 安装 ion-dist 中文翻译..." -ForegroundColor Yellow
    Copy-Item "$packDir\ion-dist\zh-CN.json" "$resourcesPath\ion-dist\i18n\zh-CN.json" -Force
    Write-Host "  ion-dist/zh-CN.json 已安装" -ForegroundColor Green

    Write-Host "[4/6] 安装 desktop-shell 中文翻译..." -ForegroundColor Yellow
    Copy-Item "$packDir\desktop-shell\zh-CN.json" "$resourcesPath\zh-CN.json" -Force
    Write-Host "  desktop-shell/zh-CN.json 已安装" -ForegroundColor Green

    Write-Host "[5/6] 安装 statsig 中文翻译..." -ForegroundColor Yellow
    Copy-Item "$packDir\statsig\zh-CN.json" "$resourcesPath\ion-dist\i18n\statsig\zh-CN.json" -Force
    Write-Host "  statsig/zh-CN.json 已安装" -ForegroundColor Green

    Write-Host "[6/6] 注册中文语言支持..." -ForegroundColor Yellow

    $jsFiles = Get-ChildItem "$resourcesPath\ion-dist\assets\v1\index-*.js" -ErrorAction SilentlyContinue

    if (-not $jsFiles) {
        Write-Host "  [警告] 未找到 index-*.js，无法自动注册 zh-CN" -ForegroundColor DarkYellow
    }

    $oldText = 'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]'
    $newText = 'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID","zh-CN"]'

    $oldPattern = [System.Text.Encoding]::UTF8.GetBytes($oldText)
    $newPattern = [System.Text.Encoding]::UTF8.GetBytes($newText)

    foreach ($jsFile in $jsFiles) {
        $bytes = [System.IO.File]::ReadAllBytes($jsFile.FullName)
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)

        if ($text.Contains('"zh-CN"')) {
            Write-Host "  语言已注册: $($jsFile.Name)" -ForegroundColor Green
            continue
        }

        if ($text.Contains($oldText)) {
            $patched = Replace-BytesInFile -FilePath $jsFile.FullName -OldPattern $oldPattern -NewPattern $newPattern

            if ($patched) {
                Write-Host "  语言注册补丁已应用: $($jsFile.Name)" -ForegroundColor Green
            }
            else {
                Write-Host "  [警告] 找到文本但补丁写入失败: $($jsFile.Name)" -ForegroundColor DarkYellow
            }
        }
        else {
            Write-Host "  [警告] 未匹配到已知语言列表，可能 Claude Desktop 已更新: $($jsFile.Name)" -ForegroundColor DarkYellow
        }
    }

    Write-Host ""
    Write-Host "=== 语言包安装完成 ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Cyan
    Write-Host "  1. 重启 Claude Desktop" -ForegroundColor White
    Write-Host "  2. 在设置中切换语言为 中文(简体)" -ForegroundColor White
    Write-Host ""
}

function Uninstall-LanguagePack {
    Write-Host "=== Claude Desktop 中文语言包卸载 ===" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "[1/4] 查找 Claude Desktop 安装路径..." -ForegroundColor Yellow
    $resourcesPath = Get-ClaudeResourcesPath

    if (-not $resourcesPath) {
        return
    }

    Write-Host "[2/4] 删除中文翻译文件..." -ForegroundColor Yellow

    Remove-Item "$resourcesPath\ion-dist\i18n\zh-CN.json" -Force -ErrorAction SilentlyContinue
    Remove-Item "$resourcesPath\zh-CN.json" -Force -ErrorAction SilentlyContinue
    Remove-Item "$resourcesPath\ion-dist\i18n\statsig\zh-CN.json" -Force -ErrorAction SilentlyContinue

    Write-Host "  翻译文件已删除" -ForegroundColor Green

    Write-Host "[3/4] 恢复语言注册..." -ForegroundColor Yellow

    $jsFiles = Get-ChildItem "$resourcesPath\ion-dist\assets\v1\index-*.js" -ErrorAction SilentlyContinue

    if (-not $jsFiles) {
        Write-Host "  [警告] 未找到 index-*.js，跳过语言注册恢复" -ForegroundColor DarkYellow
    }

    $oldPattern = [System.Text.Encoding]::UTF8.GetBytes(',"zh-CN"')
    $newPattern = [System.Text.Encoding]::UTF8.GetBytes('')

    foreach ($jsFile in $jsFiles) {
        $bytes = [System.IO.File]::ReadAllBytes($jsFile.FullName)
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)

        if ($text.Contains('"zh-CN"')) {
            $patched = Replace-BytesInFile -FilePath $jsFile.FullName -OldPattern $oldPattern -NewPattern $newPattern

            if ($patched) {
                Write-Host "  语言注册已恢复: $($jsFile.Name)" -ForegroundColor Green
            }
            else {
                Write-Host "  [警告] 未能移除 zh-CN 注册: $($jsFile.Name)" -ForegroundColor DarkYellow
            }
        }
    }

    Write-Host "[4/4] 恢复配置..." -ForegroundColor Yellow

    $configPaths = @(
        "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\config.json",
        "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude-3p\config.json"
    )

    foreach ($configPath in $configPaths) {
        if (Test-Path $configPath) {
            try {
                $config = Get-Content $configPath -Raw | ConvertFrom-Json
                $config.locale = "en-US"
                $config | ConvertTo-Json -Depth 10 | Set-Content $configPath -Encoding UTF8

                Write-Host "  配置已恢复: $configPath" -ForegroundColor Green
            }
            catch {
                Write-Host "  [警告] 配置恢复失败: $configPath" -ForegroundColor DarkYellow
                Write-Host "  $_" -ForegroundColor DarkYellow
            }
        }
    }

    Write-Host ""
    Write-Host "=== 语言包卸载完成 ===" -ForegroundColor Green
    Write-Host "请重启 Claude Desktop 使更改生效" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Usage {
    Write-Host "用法:" -ForegroundColor Cyan
    Write-Host "  .\Claude_zh-CN_LanguagePack.ps1 extract    - 提取英文文本并生成翻译模板" -ForegroundColor White
    Write-Host "  .\Claude_zh-CN_LanguagePack.ps1 install    - 安装中文语言包" -ForegroundColor White
    Write-Host "  .\Claude_zh-CN_LanguagePack.ps1 uninstall  - 卸载中文语言包" -ForegroundColor White
}

switch ($Action.ToLower()) {
    "extract" {
        Export-EnglishText
    }
    "install" {
        Install-LanguagePack
    }
    "uninstall" {
        Uninstall-LanguagePack
    }
    default {
        Show-Usage
    }
}