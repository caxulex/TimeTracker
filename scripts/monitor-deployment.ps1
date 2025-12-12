#!/usr/bin/env pwsh
# ============================================
# SCRIPT: Monitorear Deployment en AWS
# ============================================

param(
    [int]$Interval = 30,  # Segundos entre verificaciones
    [int]$MaxChecks = 20  # Máximo número de verificaciones
)

$sshKey = "C:\Users\caxul\Downloads\LightsailDefaultKey-us-east-1.pem"
$sshHost = "ubuntu@44.193.3.170"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  📊 MONITOR DE DEPLOYMENT - TimeTracker                    ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$checkCount = 0
$previousHash = ""

while ($checkCount -lt $MaxChecks) {
    $checkCount++
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    Write-Host "[$timestamp] Check #$checkCount/$MaxChecks" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    
    try {
        # Verificar último commit en el servidor
        $remoteCommit = ssh -i $sshKey $sshHost "cd ~/timetracker && git log --oneline -1 2>/dev/null" 2>$null
        
        if ($remoteCommit) {
            Write-Host "📝 Commit en servidor: $remoteCommit" -ForegroundColor White
            
            if ($remoteCommit -ne $previousHash -and $previousHash -ne "") {
                Write-Host "🔄 NUEVO DEPLOYMENT DETECTADO!" -ForegroundColor Green
            }
            $previousHash = $remoteCommit
        }
        
        # Verificar estado de contenedores
        Write-Host ""
        Write-Host "🐳 Estado de contenedores:" -ForegroundColor Cyan
        
        $containers = ssh -i $sshKey $sshHost "docker ps --format '{{.Names}}|{{.Status}}' | grep time-tracker" 2>$null
        
        if ($containers) {
            $allHealthy = $true
            foreach ($line in $containers) {
                if ($line) {
                    $parts = $line -split '\|'
                    $name = $parts[0]
                    $status = $parts[1]
                    
                    $icon = "⚪"
                    $color = "Gray"
                    
                    if ($status -match "healthy") {
                        $icon = "✅"
                        $color = "Green"
                    } elseif ($status -match "unhealthy") {
                        $icon = "❌"
                        $color = "Red"
                        $allHealthy = $false
                    } elseif ($status -match "starting") {
                        $icon = "🔄"
                        $color = "Yellow"
                        $allHealthy = $false
                    }
                    
                    Write-Host "  $icon $name" -ForegroundColor $color -NoNewline
                    Write-Host " - $status" -ForegroundColor Gray
                }
            }
            
            if ($allHealthy) {
                Write-Host ""
                Write-Host "🎉 TODOS LOS CONTENEDORES HEALTHY!" -ForegroundColor Green
                Write-Host "🌐 Aplicación disponible en: http://44.193.3.170:3000" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "✅ Deployment completado exitosamente!" -ForegroundColor Green
                break
            }
        } else {
            Write-Host "  ⚠️  No se detectaron contenedores time-tracker" -ForegroundColor Yellow
        }
        
        # Verificar conectividad
        Write-Host ""
        Write-Host "🔌 Verificando conectividad..." -ForegroundColor Cyan
        
        $backendHealth = curl -s -o $null -w "%{http_code}" "http://44.193.3.170:8080/health" 2>$null
        if ($backendHealth -eq "200") {
            Write-Host "  ✅ Backend: OK (HTTP 200)" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Backend: Error (HTTP $backendHealth)" -ForegroundColor Red
        }
        
        $frontendHealth = curl -s -o $null -w "%{http_code}" "http://44.193.3.170:3000" 2>$null
        if ($frontendHealth -eq "200") {
            Write-Host "  ✅ Frontend: OK (HTTP 200)" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Frontend: Error (HTTP $frontendHealth)" -ForegroundColor Red
        }
        
    } catch {
        Write-Host "❌ Error al verificar servidor: $_" -ForegroundColor Red
    }
    
    if ($checkCount -lt $MaxChecks) {
        Write-Host ""
        Write-Host "⏳ Esperando $Interval segundos para próxima verificación..." -ForegroundColor Gray
        Write-Host ""
        Start-Sleep -Seconds $Interval
    }
}

if ($checkCount -eq $MaxChecks) {
    Write-Host ""
    Write-Host "⏱️  Tiempo de monitoreo completado." -ForegroundColor Yellow
    Write-Host "Verifica manualmente: https://github.com/caxulex/TimeTracker/actions" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
