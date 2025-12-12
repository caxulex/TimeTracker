# 🚀 Configuración de Auto-Deploy con GitHub Actions

Este documento explica cómo configurar el despliegue automático desde GitHub a tu servidor AWS Lightsail.

## 📋 Requisitos Previos

- ✅ Repositorio en GitHub: https://github.com/caxulex/TimeTracker.git
- ✅ Servidor AWS Lightsail configurado (44.193.3.170)
- ✅ Aplicación funcionando en el servidor
- ⏳ Configuración de Secrets en GitHub (siguiente paso)

## 🔐 Paso 1: Configurar GitHub Secrets

Los secrets son variables de entorno seguras que GitHub Actions usa para conectarse a tu servidor.

### 1.1 Accede a la configuración de Secrets

1. Ve a tu repositorio en GitHub: https://github.com/caxulex/TimeTracker
2. Click en **Settings** (Configuración)
3. En el menú izquierdo, busca **Secrets and variables** > **Actions**
4. Click en **New repository secret**

### 1.2 Agrega los siguientes Secrets

#### Secret 1: `AWS_HOST`
- **Name**: `AWS_HOST`
- **Value**: `44.193.3.170`

#### Secret 2: `AWS_USERNAME`
- **Name**: `AWS_USERNAME`
- **Value**: `ubuntu`

#### Secret 3: `AWS_SSH_KEY`
- **Name**: `AWS_SSH_KEY`
- **Value**: Contenido completo de tu archivo `LightsailDefaultKey-us-east-1.pem`

**⚠️ IMPORTANTE para AWS_SSH_KEY:**
1. Abre el archivo: `C:\Users\caxul\Downloads\LightsailDefaultKey-us-east-1.pem`
2. Copia TODO el contenido (debe incluir):
   ```
   -----BEGIN RSA PRIVATE KEY-----
   [muchas líneas de texto]
   -----END RSA PRIVATE KEY-----
   ```
3. Pega todo en el campo Value del secret

## ✅ Paso 2: Verificar que los Secrets estén configurados

Después de agregar los 3 secrets, deberías ver en la página de Secrets:
- ✅ AWS_HOST
- ✅ AWS_USERNAME
- ✅ AWS_SSH_KEY

## 🔄 Paso 3: Probar el Auto-Deploy

### Opción A: Hacer un commit de prueba

```powershell
# En tu computadora local
cd "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker"

# Hacer un pequeño cambio
echo "# Auto-deploy test" >> README.md

# Commit y push
git add .
git commit -m "test: Probando auto-deploy"
git push origin master
```

### Opción B: Trigger manual desde GitHub

1. Ve a la pestaña **Actions** en GitHub
2. Selecciona el workflow **CI/CD Pipeline**
3. Click en **Run workflow**
4. Selecciona la branch `master` (o `main` si la renombraste)
5. Click en **Run workflow**

## 📊 Paso 4: Monitorear el Deployment

1. Ve a la pestaña **Actions** en tu repositorio GitHub
2. Verás el workflow corriendo con estos pasos:
   - 🧪 Backend Tests
   - 🧪 Frontend Tests
   - 🐳 Validate Docker Build
   - 🚀 Deploy to AWS Lightsail

3. Click en el workflow para ver los detalles en tiempo real

4. El deployment tomará aproximadamente 3-5 minutos:
   - ⏱️ Tests: ~2 min
   - ⏱️ Build en servidor: ~2 min
   - ⏱️ Restart contenedores: ~30 seg

## 🎯 ¿Cómo funciona el Auto-Deploy?

Cuando hagas `git push origin master`, automáticamente:

1. **GitHub Actions se activa** → Detecta el push a master
2. **Ejecuta Tests** → Backend y Frontend tests
3. **Valida Docker Build** → Verifica que las imágenes se construyan correctamente
4. **Se conecta por SSH** → Al servidor AWS usando los secrets
5. **Actualiza el código** → `git pull origin master`
6. **Reconstruye imágenes** → Docker build backend y frontend
7. **Reinicia contenedores** → Sin downtime (rolling restart)
8. **Verifica salud** → Confirma que todo esté funcionando

## 📝 Configuración Actual

### Trigger: Push a `master` o `main`
```yaml
on:
  push:
    branches: [master, main, develop]
```

### Jobs ejecutados:
1. ✅ Backend Tests (pytest, coverage)
2. ✅ Frontend Tests (vitest, build)
3. ✅ Validate Docker Build
4. 🚀 Deploy to AWS Lightsail (solo si tests pasan)

### Protecciones:
- ❌ No deploy si fallan los tests
- ✅ Automatic restart on container failure
- ✅ Health checks post-deployment
- ✅ Zero-downtime deployment strategy

## 🔍 Troubleshooting

### Error: "Host key verification failed"
**Solución**: Ya configurado en el workflow con `StrictHostKeyChecking=no`

### Error: "Permission denied (publickey)"
**Solución**: Verifica que el secret `AWS_SSH_KEY` contenga la clave completa con BEGIN y END

### Error: "Directory not found"
**Solución**: Verifica que la carpeta `~/timetracker` exista en el servidor

### El workflow no se ejecuta
**Solución**: Verifica que hayas hecho push a la branch `master` o `main`

## 🎨 Personalización

### Cambiar a otra branch
En [.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml), línea 8:
```yaml
on:
  push:
    branches: [main, develop]  # Agrega más branches
```

### Agregar notificaciones
Puedes agregar notificaciones de Slack/Discord/Email al final del workflow:
```yaml
- name: Notify success
  if: success()
  run: echo "Deployment successful!"
```

### Deploy manual (sin tests)
Crea un nuevo workflow `.github/workflows/deploy-only.yml`:
```yaml
name: Deploy Only
on:
  workflow_dispatch:
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1.0.0
        with:
          # ... mismo script de deploy
```

## 📚 Recursos Adicionales

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [SSH Action Documentation](https://github.com/appleboy/ssh-action)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

## 🆘 Soporte

Si tienes problemas:
1. Revisa los logs en la pestaña **Actions** de GitHub
2. Verifica que los 3 secrets estén configurados correctamente
3. Prueba conectarte manualmente por SSH al servidor

---

**✅ Una vez configurado, cada push a `master` desplegará automáticamente tu aplicación!**
