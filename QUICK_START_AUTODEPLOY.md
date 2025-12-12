# ⚡ GUÍA RÁPIDA: Configurar GitHub Secrets (3 minutos)

## ✅ ¡Tu SSH Key ya está en el portapapeles!

Sigue estos pasos **EXACTAMENTE**:

---

## 🔐 PASO 1: Crear Secret #1 - AWS_HOST

1. En la página que se abrió (o ve a): https://github.com/caxulex/TimeTracker/settings/secrets/actions
2. Click en el botón verde **"New repository secret"**
3. Llena el formulario:
   - **Name**: `AWS_HOST`
   - **Secret**: `44.193.3.170`
4. Click en **"Add secret"**

✅ **Listo! 1/3 completado**

---

## 🔐 PASO 2: Crear Secret #2 - AWS_USERNAME

1. Click nuevamente en **"New repository secret"**
2. Llena el formulario:
   - **Name**: `AWS_USERNAME`
   - **Secret**: `ubuntu`
3. Click en **"Add secret"**

✅ **Listo! 2/3 completado**

---

## 🔐 PASO 3: Crear Secret #3 - AWS_SSH_KEY

### ⚠️ IMPORTANTE: Tu clave SSH está en el portapapeles

1. Click nuevamente en **"New repository secret"**
2. Llena el formulario:
   - **Name**: `AWS_SSH_KEY`
   - **Secret**: Presiona **Ctrl+V** para pegar la clave completa
3. **VERIFICA** que el secret comience con: `-----BEGIN RSA PRIVATE KEY-----`
4. **VERIFICA** que el secret termine con: `-----END RSA PRIVATE KEY-----`
5. Click en **"Add secret"**

✅ **Listo! 3/3 completado**

---

## 🎯 VERIFICACIÓN FINAL

Después de agregar los 3 secrets, deberías ver en la lista:

```
Repository secrets (3)
━━━━━━━━━━━━━━━━━━━━━━
• AWS_HOST           Updated X seconds ago
• AWS_SSH_KEY        Updated X seconds ago  
• AWS_USERNAME       Updated X seconds ago
```

---

## 🚀 PROBAR EL AUTO-DEPLOY

### Opción 1: Hacer un commit de prueba

```powershell
cd "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker"
echo "`n# Auto-deploy configurado $(Get-Date)" >> README.md
git add README.md
git commit -m "test: Probar auto-deploy"
git push origin master
```

Luego ve a: https://github.com/caxulex/TimeTracker/actions

---

### Opción 2: Ejecutar manualmente

1. Ve a: https://github.com/caxulex/TimeTracker/actions
2. Click en el workflow **"CI/CD Pipeline"** (en la lista izquierda)
3. Click en **"Run workflow"** (botón azul)
4. Selecciona branch **"master"**
5. Click en **"Run workflow"**

---

## 📊 MONITOREAR EL DEPLOYMENT

En https://github.com/caxulex/TimeTracker/actions verás:

```
✓ Backend Tests         (~2 min)
✓ Frontend Tests        (~2 min)
✓ Validate Docker       (~1 min)
🚀 Deploy to AWS        (~3 min)
   ├─ Pull code
   ├─ Build images
   ├─ Restart containers
   └─ Health check
```

**Tiempo total**: ~8 minutos

---

## ✅ CONFIRMACIÓN DE ÉXITO

Cuando termine el deployment, verás:

```
✅ Deployment completed successfully!
🌐 Application available at: http://44.193.3.170:3000
```

Y en tu servidor, los contenedores estarán actualizados automáticamente!

---

## 🎉 ¡LISTO!

Ahora **cada vez que hagas push a master**, tu aplicación se desplegará automáticamente en AWS.

**Workflow completo**:
```
Código local → git push → GitHub Actions → Tests → Build → Deploy AWS → App actualizada
```

---

## 🆘 ¿Problemas?

### "Workflow didn't run"
- Verifica que pusheaste a la branch `master`
- Revisa que los 3 secrets estén configurados

### "Deploy failed"
- Ve a Actions y click en el workflow fallido
- Lee el log de error
- Los errores más comunes:
  - Secret mal configurado
  - SSH key incompleta
  - Permisos de archivo .pem

### "Can't connect to server"
- Verifica que el servidor esté encendido
- Prueba conectarte manualmente: `ssh -i "C:\Users\caxul\Downloads\LightsailDefaultKey-us-east-1.pem" ubuntu@44.193.3.170`

---

**📚 Documentación completa**: Ver [GITHUB_AUTODEPLOY_SETUP.md](GITHUB_AUTODEPLOY_SETUP.md)
