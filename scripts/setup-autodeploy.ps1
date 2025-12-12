#!/usr/bin/env pwsh
# ============================================
# SCRIPT: Configurar Auto-Deploy en GitHub
# ============================================

Write-Host ""
Write-Host "🚀 CONFIGURACIÓN DE AUTO-DEPLOY - TimeTracker" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 PASO 1: Verificar archivos actualizados" -ForegroundColor Yellow
Write-Host ""

# Verificar que los archivos necesarios existan
$workflowFile = ".github/workflows/ci-cd.yml"
$guideFile = "GITHUB_AUTODEPLOY_SETUP.md"

if (Test-Path $workflowFile) {
    Write-Host "✅ Workflow de GitHub Actions: $workflowFile" -ForegroundColor Green
} else {
    Write-Host "❌ Falta: $workflowFile" -ForegroundColor Red
    exit 1
}

if (Test-Path $guideFile) {
    Write-Host "✅ Guía de configuración: $guideFile" -ForegroundColor Green
} else {
    Write-Host "❌ Falta: $guideFile" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 PASO 2: Commit y Push a GitHub" -ForegroundColor Yellow
Write-Host ""

# Git add
Write-Host "Agregando archivos..." -ForegroundColor Gray
git add .github/workflows/ci-cd.yml
git add GITHUB_AUTODEPLOY_SETUP.md
git add scripts/setup-autodeploy.ps1

# Git commit
Write-Host "Creando commit..." -ForegroundColor Gray
git commit -m "feat: Configurar auto-deploy desde GitHub Actions a AWS Lightsail

- Actualizar workflow ci-cd.yml con deploy a producción
- Agregar script SSH para deployment automático
- Crear guía completa GITHUB_AUTODEPLOY_SETUP.md
- Auto-deploy se activa con push a main
- Tests ejecutados antes de deploy
- Zero-downtime deployment strategy"

# Git push
Write-Host "Subiendo a GitHub..." -ForegroundColor Gray
git push origin main

Write-Host ""
Write-Host "✅ Cambios subidos a GitHub exitosamente!" -ForegroundColor Green
Write-Host ""

Write-Host "🔐 PASO 3: Configurar Secrets en GitHub" -ForegroundColor Yellow
Write-Host ""
Write-Host "Ahora necesitas configurar 3 secrets en GitHub:" -ForegroundColor White
Write-Host ""
Write-Host "1. Ve a: https://github.com/caxulex/TimeTracker/settings/secrets/actions" -ForegroundColor White
Write-Host ""
Write-Host "2. Crea estos 3 secrets:" -ForegroundColor White
Write-Host "   • AWS_HOST = 44.193.3.170" -ForegroundColor Cyan
Write-Host "   • AWS_USERNAME = ubuntu" -ForegroundColor Cyan
Write-Host "   • AWS_SSH_KEY = [contenido completo del archivo .pem]" -ForegroundColor Cyan
Write-Host ""

Write-Host "📄 Para copiar tu SSH key al portapapeles:" -ForegroundColor Yellow
$keyPath = "C:\Users\caxul\Downloads\LightsailDefaultKey-us-east-1.pem"
if (Test-Path $keyPath) {
    Write-Host "Ejecuta este comando:" -ForegroundColor White
    Write-Host "   Get-Content '$keyPath' | Set-Clipboard" -ForegroundColor Green
    Write-Host ""
    Write-Host "¿Quieres copiar la SSH key al portapapeles ahora? (S/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -eq "S" -or $response -eq "s") {
        Get-Content $keyPath | Set-Clipboard
        Write-Host "✅ SSH key copiada al portapapeles!" -ForegroundColor Green
        Write-Host "Ahora puedes pegarla (Ctrl+V) en GitHub como secret AWS_SSH_KEY" -ForegroundColor White
    }
} else {
    Write-Host "⚠️  No se encontró la key en: $keyPath" -ForegroundColor Red
}

Write-Host ""
Write-Host "📖 PASO 4: Revisar la guía completa" -ForegroundColor Yellow
Write-Host ""
Write-Host "Lee el archivo: GITHUB_AUTODEPLOY_SETUP.md" -ForegroundColor White
Write-Host "Contiene:" -ForegroundColor White
Write-Host "  • Instrucciones paso a paso" -ForegroundColor Gray
Write-Host "  • Screenshots de referencia" -ForegroundColor Gray
Write-Host "  • Troubleshooting" -ForegroundColor Gray
Write-Host "  • Cómo probar el auto-deploy" -ForegroundColor Gray

Write-Host ""
Write-Host "✅ CONFIGURACIÓN COMPLETADA" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 Próximos pasos:" -ForegroundColor Cyan
Write-Host "1. Configura los 3 secrets en GitHub (instrucciones arriba)" -ForegroundColor White
Write-Host "2. Haz un commit de prueba: git commit -m 'test' && git push" -ForegroundColor White
Write-Host "3. Ve a GitHub Actions para ver el deploy en vivo" -ForegroundColor White
Write-Host ""
Write-Host "🌐 Después del primer deploy automático, tu app estará en:" -ForegroundColor Cyan
Write-Host "   http://44.193.3.170:3000" -ForegroundColor Green
Write-Host ""
