# 🚀 Guía Completa de Despliegue a AWS Lightsail
## TimeTracker - timetracker.shaemarcus.com

---

## 📋 Información del Servidor

**Subdominio:** timetracker.shaemarcus.com  
**IP Pública:** 44.193.3.170  
**IP Pública IPv6:** 2600:1f18:e3d:8b00:6fe7:c2ca:76e7:dd2c  
**Usuario:** ubuntu  
**Sistema:** Ubuntu 24.04.3 LTS  
**Recursos:** 2 GB RAM, 2 vCPUs, 60 GB SSD  
**Región:** us-east-1a (Virginia)

---

## 🎯 Resumen del Plan de Despliegue

1. Preparar y actualizar el servidor
2. Instalar Docker y Docker Compose
3. Configurar DNS para timetracker.shaemarcus.com
4. Transferir archivos del proyecto
5. Configurar variables de entorno con el nuevo dominio
6. Actualizar configuración de la aplicación para el subdominio
7. Construir e iniciar contenedores
8. Inicializar base de datos
9. Configurar firewall en AWS Lightsail
10. Configurar SSL/TLS con Caddy (paso posterior)

---

## 🔧 PASO 1: Preparar el Servidor

### 1.1 Conectarse al Servidor

**Desde tu máquina local (Windows PowerShell):**
```powershell
# Asegúrate de tener la clave SSH descargada
# Guárdala en: C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem

ssh -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" ubuntu@44.193.3.170
```

### 1.2 Actualizar el Sistema
```bash
sudo apt update
sudo apt upgrade -y

# El sistema requiere reinicio
sudo reboot
```

**⏳ Espera 2-3 minutos después del reinicio y reconéctate:**
```powershell
ssh -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" ubuntu@44.193.3.170
```

---

## 🐳 PASO 2: Instalar Docker y Docker Compose

### 2.1 Instalar Docker
```bash
# Instalar dependencias necesarias
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Agregar Docker GPG key oficial
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Agregar repositorio Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Actualizar e instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Agregar usuario ubuntu al grupo docker (evita usar sudo)
sudo usermod -aG docker ubuntu

# Recargar grupos (o cerrar sesión y reconectar)
newgrp docker

# Verificar instalación
docker --version
docker run hello-world
```

### 2.2 Instalar Docker Compose
```bash
# Descargar Docker Compose v2.24.0
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permisos de ejecución
sudo chmod +x /usr/local/bin/docker-compose

# Verificar instalación
docker-compose --version
```

---

## 🌐 PASO 3: Configurar DNS para timetracker.shaemarcus.com

### 3.1 Acceder al Panel de Control de DNS

**Proveedor de dominio:** Donde esté registrado shaemarcus.com (GoDaddy, Namecheap, Cloudflare, etc.)

### 3.2 Agregar Registros DNS

**Registros a crear:**

| Tipo | Nombre | Valor | TTL |
|------|--------|-------|-----|
| A | timetracker | 44.193.3.170 | 3600 |
| AAAA | timetracker | 2600:1f18:e3d:8b00:6fe7:c2ca:76e7:dd2c | 3600 |

**Ejemplo para diferentes proveedores:**

**GoDaddy:**
1. Ve a "Mis productos" → "DNS" en shaemarcus.com
2. Click "Agregar" → Selecciona "A"
3. Host: `timetracker`
4. Apunta a: `44.193.3.170`
5. TTL: 1 hora
6. Guardar

**Cloudflare:**
1. Dashboard → DNS → Agregar registro
2. Tipo: A
3. Nombre: timetracker
4. IPv4: 44.193.3.170
5. Proxy status: DNS only (nube gris)
6. Guardar

### 3.3 Verificar Propagación DNS

```bash
# Desde el servidor AWS
dig timetracker.shaemarcus.com

# Desde tu máquina Windows
nslookup timetracker.shaemarcus.com
```

**⏳ La propagación DNS puede tardar de 5 minutos a 24 horas**

---

## 📦 PASO 4: Transferir Archivos del Proyecto

### 4.1 Crear Directorio en el Servidor

**En el servidor AWS:**
```bash
mkdir -p ~/timetracker
cd ~/timetracker
```

### 4.2 Preparar Archivos Localmente

**En tu máquina Windows (PowerShell):**
```powershell
# Navega a la carpeta del proyecto
cd "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker"

# Crear archivo comprimido excluyendo archivos innecesarios
tar -czf timetracker.tar.gz `
  --exclude=node_modules `
  --exclude=.git `
  --exclude=.venv `
  --exclude=__pycache__ `
  --exclude=frontend/dist `
  --exclude=frontend/node_modules `
  --exclude=backend/__pycache__ `
  --exclude=*.pyc `
  .
```

### 4.3 Transferir al Servidor

**Desde Windows PowerShell:**
```powershell
# Transferir archivo comprimido
scp -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" `
  timetracker.tar.gz `
  ubuntu@44.193.3.170:~/timetracker/

# Limpiar archivo local (opcional)
Remove-Item timetracker.tar.gz
```

### 4.4 Extraer Archivos en el Servidor

**En el servidor AWS:**
```bash
cd ~/timetracker
tar -xzf timetracker.tar.gz
rm timetracker.tar.gz
ls -la
```

---

## 🔐 PASO 5: Configurar Variables de Entorno

### 5.1 Generar JWT Secret Seguro

```bash
# Generar clave secreta de 32 bytes
openssl rand -hex 32
```

**Copia el resultado, lo necesitarás en el siguiente paso**

### 5.2 Crear Archivo .env para Backend

```bash
cd ~/timetracker/backend

cat > .env << 'EOF'
# Base de datos PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgres@time-tracker-postgres:5432/time_tracker

# Seguridad JWT
JWT_SECRET=PEGA_AQUI_LA_CLAVE_GENERADA_EN_EL_PASO_ANTERIOR
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS - Permitir acceso desde el dominio
ALLOWED_ORIGINS=https://timetracker.shaemarcus.com,http://timetracker.shaemarcus.com

# Redis para cache y sesiones
REDIS_URL=redis://time-tracker-redis:6379

# Configuración de entorno
ENVIRONMENT=production
DEBUG=False
EOF
```

**⚠️ IMPORTANTE:** Reemplaza `PEGA_AQUI_LA_CLAVE_GENERADA_EN_EL_PASO_ANTERIOR` con el JWT_SECRET generado

### 5.3 Crear Archivo .env.production para Frontend

```bash
cd ~/timetracker/frontend

cat > .env.production << 'EOF'
# API Backend URL
VITE_API_URL=https://timetracker.shaemarcus.com/api
EOF
```

### 5.4 Verificar Archivos de Entorno

```bash
# Verificar backend
cat ~/timetracker/backend/.env

# Verificar frontend
cat ~/timetracker/frontend/.env.production
```

---

## ⚙️ PASO 6: Actualizar Configuración de la Aplicación

### 6.1 Actualizar docker-compose.yml

**Si es necesario, actualiza las variables de entorno en docker-compose.yml:**

```bash
cd ~/timetracker

# Editar docker-compose.yml
nano docker-compose.yml
```

**Verificar que tenga estas configuraciones:**
- Backend usa puerto 8080
- Frontend usa puerto 80
- PostgreSQL usa puerto interno 5432
- Redis usa puerto interno 6379

### 6.2 Verificar nginx.conf del Frontend

```bash
cat ~/timetracker/frontend/nginx.conf
```

**Debe incluir configuración para proxy reverso:**
```nginx
location /api/ {
    proxy_pass http://timetracker-backend:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /ws {
    proxy_pass http://timetracker-backend:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### 6.3 Actualizar CORS en el Backend (si es necesario)

**Verificar que backend/app/main.py incluye CORS para el dominio:**

```bash
cd ~/timetracker/backend/app
grep -A 10 "CORSMiddleware" main.py
```

**Debe permitir:**
- https://timetracker.shaemarcus.com
- http://timetracker.shaemarcus.com

---

## 🏗️ PASO 7: Construir e Iniciar Contenedores

### 7.1 Construir Imagen del Backend

```bash
cd ~/timetracker

# Construir imagen backend
docker build -t timetracker-backend ./backend

# Verificar imagen creada
docker images | grep timetracker-backend
```

### 7.2 Construir Imagen del Frontend

```bash
# Construir imagen frontend con variables de producción
docker build -t timetracker-frontend ./frontend

# Verificar imagen creada
docker images | grep timetracker-frontend
```

### 7.3 Iniciar Todos los Contenedores

```bash
cd ~/timetracker

# Iniciar todos los servicios
docker compose up -d

# Ver estado de contenedores
docker ps
```

**Deberías ver 4 contenedores corriendo:**
- timetracker-frontend (puerto 80)
- timetracker-backend (puerto 8080)
- time-tracker-postgres (puerto 5432)
- time-tracker-redis (puerto 6379)

### 7.4 Verificar Logs

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs individuales
docker logs timetracker-backend -f
docker logs timetracker-frontend -f
docker logs time-tracker-postgres
docker logs time-tracker-redis

# Para salir de logs: Ctrl+C
```

---

## 🗄️ PASO 8: Inicializar Base de Datos

### 8.1 Esperar que PostgreSQL Esté Listo

```bash
# Verificar que postgres esté saludable
docker ps | grep postgres

# Ver logs de postgres
docker logs time-tracker-postgres
```

### 8.2 Ejecutar Script de Seed

```bash
docker exec timetracker-backend python -m app.seed
```

**Resultado esperado:**
```
Seeding database...
Created 4 users
Created 2 teams
Created 5 team memberships
Created 3 projects
Created 11 tasks
Created 20 time entries

✅ Database seeded successfully!

Test accounts:
  Admin: admin@timetracker.com / admin123
  User:  john@example.com / password123
  User:  jane@example.com / password123
  User:  bob@example.com / password123
```

### 8.3 Verificar Datos en la Base de Datos

```bash
# Conectarse a PostgreSQL
docker exec -it time-tracker-postgres psql -U postgres -d time_tracker

# Dentro de psql:
\dt                                    # Listar tablas
SELECT COUNT(*) FROM users;            # Verificar usuarios
SELECT email, role FROM users;         # Ver usuarios creados
\q                                     # Salir
```

---

## 🔥 PASO 9: Configurar Firewall en AWS Lightsail

### 9.1 Acceder a la Consola de AWS Lightsail

1. Ve a: https://lightsail.aws.amazon.com/
2. Selecciona tu instancia: **n8n-main-server**
3. Click en la pestaña **"Networking"**

### 9.2 Configurar Reglas de Firewall IPv4

**Scroll hasta "IPv4 Firewall" y agrega estas reglas:**

| Application | Protocol | Port | From |
|-------------|----------|------|------|
| SSH | TCP | 22 | 0.0.0.0/0 |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |
| Custom | TCP | 8080 | 0.0.0.0/0 |

**Cómo agregar cada regla:**
1. Click en "+ Add rule"
2. Selecciona el tipo o "Custom"
3. Especifica el puerto
4. Deja "Any" para permitir desde cualquier IP
5. Click "Create"

### 9.3 Configurar Reglas de Firewall IPv6 (Opcional)

Si planeas usar IPv6:
1. Scroll a "IPv6 Firewall"
2. Agrega las mismas reglas (80, 443)

---

## ✅ PASO 10: Verificar Funcionamiento

### 10.1 Probar Backend Directamente

```bash
# Health check
curl http://localhost:8080/health

# Debe responder: {"status":"healthy"}
```

### 10.2 Probar Frontend Localmente

```bash
# Ver página principal
curl http://localhost

# Debe devolver HTML
```

### 10.3 Probar desde IP Pública

**Desde tu navegador o máquina Windows:**
```powershell
# Probar backend
Invoke-RestMethod -Uri "http://44.193.3.170:8080/health"

# Probar frontend
Start-Process "http://44.193.3.170"
```

### 10.4 Probar Login desde IP

**Abre en tu navegador:**
```
http://44.193.3.170
```

**Intenta iniciar sesión:**
- Email: `admin@timetracker.com`
- Password: `admin123`

**✅ Si el login funciona, la aplicación está operativa**

---

## 🔒 PASO 11: Configurar SSL/TLS con Caddy (Próximo Paso)

**⚠️ Este paso se realizará después**

Una vez que el DNS esté propagado y puedas acceder a `http://timetracker.shaemarcus.com`, se procederá a:

1. Configurar Caddy como proxy reverso
2. Obtener certificados SSL automáticamente
3. Redirigir HTTP a HTTPS
4. Configurar headers de seguridad

**Requisitos previos:**
- DNS propagado (timetracker.shaemarcus.com apunta a 44.193.3.170)
- Aplicación funcionando en http://44.193.3.170
- Puerto 80 y 443 abiertos en firewall

---

## 📊 PASO 12: Monitoreo y Mantenimiento

### 12.1 Comandos Útiles para Monitoreo

```bash
# Ver estado de todos los contenedores
docker ps -a

# Ver uso de recursos en tiempo real
docker stats

# Ver logs en tiempo real
docker compose logs -f

# Ver espacio en disco
df -h
docker system df
```

### 12.2 Comandos de Control de la Aplicación

```bash
# Detener todos los contenedores
cd ~/timetracker
docker compose down

# Iniciar todos los contenedores
docker compose up -d

# Reiniciar todos los contenedores
docker compose restart

# Reiniciar solo un servicio
docker compose restart backend
docker compose restart frontend

# Ver logs de un servicio específico
docker compose logs backend -f
docker compose logs frontend -f
```

### 12.3 Backup de Base de Datos

```bash
# Crear backup
docker exec time-tracker-postgres pg_dump -U postgres time_tracker > backup_$(date +%Y%m%d_%H%M%S).sql

# Listar backups
ls -lh ~/timetracker/backup_*.sql

# Restaurar backup
cat backup_20251212_150000.sql | docker exec -i time-tracker-postgres psql -U postgres -d time_tracker
```

### 12.4 Actualizar la Aplicación

```bash
# 1. Detener contenedores
cd ~/timetracker
docker compose down

# 2. Respaldar base de datos
docker compose up -d postgres
docker exec time-tracker-postgres pg_dump -U postgres time_tracker > backup_before_update.sql
docker compose down

# 3. Actualizar código (transferir nuevos archivos)
# ... transferencia de archivos ...

# 4. Reconstruir imágenes
docker build -t timetracker-backend ./backend
docker build -t timetracker-frontend ./frontend

# 5. Reiniciar
docker compose up -d

# 6. Ver logs
docker compose logs -f
```

---

## 🚨 Solución de Problemas Comunes

### Problema 1: Backend no conecta a PostgreSQL

**Síntoma:** Error "could not connect to server"

**Solución:**
```bash
# Verificar que postgres esté corriendo
docker ps | grep postgres

# Ver logs de postgres
docker logs time-tracker-postgres

# Verificar variable de entorno
docker exec timetracker-backend env | grep DATABASE_URL

# Reiniciar servicios
docker compose restart postgres
docker compose restart backend
```

### Problema 2: Frontend muestra página blanca

**Síntoma:** Pantalla blanca al acceder

**Solución:**
```bash
# Ver logs del frontend
docker logs timetracker-frontend

# Ver logs del nginx
docker exec timetracker-frontend cat /var/log/nginx/error.log

# Reconstruir frontend
docker compose down
docker rmi timetracker-frontend
docker build -t timetracker-frontend ./frontend
docker compose up -d
```

### Problema 3: WebSocket no conecta

**Síntoma:** Errores de WebSocket en consola del navegador

**Solución:**
```bash
# Verificar configuración de nginx
docker exec timetracker-frontend cat /etc/nginx/conf.d/default.conf

# Verificar backend logs
docker logs timetracker-backend | grep -i websocket

# Verificar que el puerto 8080 esté accesible
curl http://localhost:8080/health
```

### Problema 4: Aplicación lenta

**Síntoma:** Páginas tardan mucho en cargar

**Solución:**
```bash
# Ver uso de recursos
docker stats

# Ver memoria del sistema
free -h

# Ver espacio en disco
df -h

# Limpiar imágenes no usadas
docker system prune -a

# Verificar logs de base de datos
docker logs time-tracker-postgres | tail -100
```

### Problema 5: Puerto 80 ya está en uso

**Síntoma:** Error "port is already allocated"

**Solución:**
```bash
# Ver qué proceso usa el puerto 80
sudo lsof -i :80
sudo netstat -tulpn | grep :80

# Si es nginx u otro servicio, detenerlo
sudo systemctl stop nginx
sudo systemctl stop apache2

# Luego iniciar contenedores
docker compose up -d
```

---

## 📋 Checklist de Despliegue

**Pre-despliegue:**
- [ ] Servidor AWS Lightsail accesible vía SSH
- [ ] DNS configurado (timetracker.shaemarcus.com → 44.193.3.170)
- [ ] DNS propagado (verificado con dig/nslookup)

**Instalación:**
- [ ] Sistema actualizado (apt update && apt upgrade)
- [ ] Docker instalado y funcionando
- [ ] Docker Compose instalado
- [ ] Usuario agregado al grupo docker

**Configuración:**
- [ ] Archivos del proyecto transferidos
- [ ] Backend .env creado con JWT_SECRET seguro
- [ ] Frontend .env.production creado con dominio correcto
- [ ] CORS configurado en backend

**Construcción:**
- [ ] Imagen backend construida exitosamente
- [ ] Imagen frontend construida exitosamente
- [ ] Todos los contenedores iniciados (4/4)
- [ ] Sin errores en logs

**Base de Datos:**
- [ ] PostgreSQL saludable
- [ ] Script de seed ejecutado
- [ ] Usuarios creados (4 usuarios)
- [ ] Datos de prueba insertados

**Seguridad:**
- [ ] Firewall configurado en AWS (puertos 22, 80, 443, 8080)
- [ ] JWT_SECRET único y seguro
- [ ] Contraseñas de producción configuradas

**Verificación:**
- [ ] Backend responde en http://44.193.3.170:8080/health
- [ ] Frontend carga en http://44.193.3.170
- [ ] Login funciona con admin@timetracker.com
- [ ] No hay errores en consola del navegador

**Pendiente (próximo paso):**
- [ ] Caddy configurado como proxy reverso
- [ ] SSL/TLS configurado
- [ ] timetracker.shaemarcus.com accesible vía HTTPS

---

## 🎯 URLs Finales

### Durante Despliegue (Sin SSL):
- **Frontend:** http://44.193.3.170
- **Backend API:** http://44.193.3.170:8080
- **Health Check:** http://44.193.3.170:8080/health

### Después de Configurar Caddy (Con SSL):
- **Aplicación:** https://timetracker.shaemarcus.com
- **Backend API:** https://timetracker.shaemarcus.com/api
- **WebSocket:** wss://timetracker.shaemarcus.com/ws

---

## 👥 Credenciales de Acceso

### Aplicación Web:
- **Admin:** admin@timetracker.com / admin123
- **Usuario 1:** john@example.com / password123
- **Usuario 2:** jane@example.com / password123
- **Usuario 3:** bob@example.com / password123

### Base de Datos PostgreSQL:
- **Host:** localhost (dentro de contenedores) o 44.193.3.170:5432 (externo)
- **Base de datos:** time_tracker
- **Usuario:** postgres
- **Contraseña:** postgres

### Redis:
- **Host:** localhost (dentro de contenedores) o 44.193.3.170:6379 (externo)
- **Sin contraseña**

### Servidor SSH:
- **Host:** 44.193.3.170
- **Usuario:** ubuntu
- **Clave:** LightsailDefaultKey-us-east-1.pem

---

## 📞 Soporte y Siguientes Pasos

**Siguiente sesión:**
1. Verificar que DNS está propagado
2. Confirmar acceso a http://timetracker.shaemarcus.com
3. Configurar Caddy para SSL/TLS automático
4. Probar HTTPS y renovación de certificados
5. Configurar monitoreo y alertas

**Documentación adicional:**
- [SESSION_REPORT_DEC_12_2025.md](./SESSION_REPORT_DEC_12_2025.md) - Reporte completo de la sesión de desarrollo
- [TIMEZONE_ASSESSMENT.md](./TIMEZONE_ASSESSMENT.md) - Auditoría de timezone
- [PAYROLL_FIX_SUMMARY.md](./PAYROLL_FIX_SUMMARY.md) - Documentación del sistema de nómina
- [ADMIN_REPORTS_QUICK_GUIDE.md](./ADMIN_REPORTS_QUICK_GUIDE.md) - Guía de reportes admin

---

**Última actualización:** 12 de diciembre de 2025  
**Estado de la aplicación:** 🟢 Lista para despliegue  
**Próximo hito:** Configuración de SSL/TLS con Caddy
