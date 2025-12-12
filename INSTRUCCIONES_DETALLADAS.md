# 📖 INSTRUCCIONES DETALLADAS DE DESPLIEGUE
## TimeTracker en AWS Lightsail - Paso a Paso

---

## 🎯 LO QUE VAS A HACER

Este documento te guía **EXACTAMENTE** paso a paso para subir TimeTracker a AWS. No asume que sabes nada, todo está explicado.

**Duración estimada:** 45-60 minutos

---

## 📋 ANTES DE EMPEZAR

### ¿Qué vas a necesitar?

1. ✅ Tu computadora Windows con PowerShell
2. ✅ Acceso a AWS Lightsail (ya tienes el servidor n8n-main-server)
3. ✅ La clave SSH descargada (LightsailDefaultKey-us-east-1.pem)
4. ✅ Acceso al panel de control de tu dominio shaemarcus.com
5. ✅ 60 GB de espacio libre en tu computadora (para el archivo comprimido)

---

## 🚀 PARTE 1: CONFIGURAR DNS (5-10 minutos)

### ¿Qué es esto?
Vamos a hacer que `timetracker.shaemarcus.com` apunte a tu servidor AWS.

### Paso 1: Identifica dónde está tu dominio

**¿Dónde compraste shaemarcus.com?** 
- GoDaddy
- Namecheap
- Cloudflare
- Google Domains
- Otro

### Paso 2A: Si tu dominio está en GoDaddy

1. **Abre tu navegador** (Chrome, Firefox, Edge, etc.)
2. **Ve a:** https://account.godaddy.com
3. **Inicia sesión** con tu cuenta de GoDaddy
4. **Busca** en la página donde dice "Mis Productos" o "My Products"
5. **Encuentra** shaemarcus.com en la lista de dominios
6. **Haz clic** en el botón que dice "DNS" o "Administrar DNS"

Ahora verás una tabla con registros DNS. Sigue estos pasos:

7. **Busca** el botón "Agregar" o "Add" (generalmente está arriba o abajo de la tabla)
8. **Haz clic** en "Agregar"
9. **Selecciona** "A" en el tipo de registro
10. **Escribe** en cada campo:
    - **Host/Nombre:** `timetracker`
    - **Apunta a/Points to:** `44.193.3.170`
    - **TTL:** `1 hora` o `3600`
11. **Haz clic** en "Guardar" o "Save"
12. **LISTO** - Espera 5-30 minutos para que se propague

### Paso 2B: Si tu dominio está en Cloudflare

1. **Abre tu navegador**
2. **Ve a:** https://dash.cloudflare.com
3. **Inicia sesión**
4. **Haz clic** en el dominio `shaemarcus.com`
5. **Haz clic** en la pestaña "DNS"
6. **Haz clic** en el botón azul "Add record"
7. **Llena los campos:**
    - **Type:** Selecciona "A"
    - **Name:** Escribe `timetracker`
    - **IPv4 address:** Escribe `44.193.3.170`
    - **Proxy status:** Haz clic para que la nube esté GRIS (DNS only)
    - **TTL:** Deja "Auto"
8. **Haz clic** en "Save"
9. **LISTO** - Espera 5-30 minutos

### Paso 2C: Si tu dominio está en Namecheap

1. **Abre tu navegador**
2. **Ve a:** https://www.namecheap.com
3. **Inicia sesión**
4. **Haz clic** en "Domain List" en el menú izquierdo
5. **Busca** shaemarcus.com y haz clic en "Manage"
6. **Haz clic** en la pestaña "Advanced DNS"
7. **Haz clic** en "Add New Record"
8. **Llena los campos:**
    - **Type:** Selecciona "A Record"
    - **Host:** Escribe `timetracker`
    - **Value:** Escribe `44.193.3.170`
    - **TTL:** Selecciona "Automatic" o "1 hour"
9. **Haz clic** en el ícono del ✓ (checkmark) verde para guardar
10. **LISTO** - Espera 5-30 minutos

### Paso 3: Verificar que el DNS funciona

**IMPORTANTE:** Espera al menos 10 minutos después de guardar el DNS.

1. **Abre PowerShell** (Inicio → Escribe "PowerShell" → Enter)
2. **Copia y pega** este comando:
   ```powershell
   nslookup timetracker.shaemarcus.com
   ```
3. **Presiona** Enter
4. **Deberías ver:** `44.193.3.170` en la respuesta

**Si NO ves la IP:**
- Espera 10-20 minutos más
- Vuelve a intentar
- Si después de 1 hora no funciona, verifica que guardaste correctamente en el Paso 2

**Si VES la IP:** ✅ ¡Perfecto! Continúa al siguiente paso

---

## 💻 PARTE 2: PREPARAR TU COMPUTADORA (10 minutos)

### Paso 1: Ubicar la Clave SSH

La clave SSH es un archivo que te permite conectarte al servidor de forma segura.

1. **Abre** el Explorador de Archivos (ícono de carpeta en la barra de tareas)
2. **Ve a** tu carpeta de Descargas (generalmente `C:\Users\TuNombre\Downloads`)
3. **Busca** un archivo llamado `LightsailDefaultKey-us-east-1.pem`

**¿No lo encuentras?**
- Ve a AWS Lightsail: https://lightsail.aws.amazon.com
- Haz clic en "Account" (esquina superior derecha)
- Haz clic en "SSH keys"
- Busca "Virginia (us-east-1)"
- Haz clic en "Download"

### Paso 2: Mover la Clave SSH a una Ubicación Segura

1. **En el Explorador de Archivos**, ve a `C:\Users\caxul`
2. **Haz clic derecho** en un espacio vacío
3. **Selecciona** "Nueva carpeta" o "New folder"
4. **Escribe** `.ssh` como nombre (con el punto al inicio)
5. **Presiona** Enter
6. **Arrastra** el archivo `LightsailDefaultKey-us-east-1.pem` desde Descargas a la carpeta `.ssh`

### Paso 3: Crear el Archivo Comprimido del Proyecto

1. **Abre PowerShell** (Inicio → Escribe "PowerShell" → Clic derecho → "Ejecutar como administrador")
2. **Copia y pega** CADA línea, UNA POR UNA:

```powershell
cd "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker"
```
Presiona Enter, espera a que aparezca el prompt de nuevo.

```powershell
tar -czf timetracker.tar.gz --exclude=node_modules --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=frontend/dist --exclude=frontend/node_modules --exclude=backend/__pycache__ --exclude=*.pyc .
```
Presiona Enter. **ESTO TARDARÁ 2-5 MINUTOS**. Verás que el cursor parpadea, es normal.

3. **Cuando termine**, verás el prompt de nuevo (`PS C:\...>`)
4. **Verifica** que se creó el archivo:
```powershell
ls timetracker.tar.gz
```

Deberías ver algo como:
```
Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---          12/12/2025   2:30 PM      15234567 timetracker.tar.gz
```

✅ **Si ves el archivo:** Perfecto, continúa.
❌ **Si dice "no se encuentra":** Vuelve a intentar el comando `tar -czf...`

---

## 🔐 PARTE 3: CONECTARSE AL SERVIDOR (5 minutos)

### Paso 1: Abrir PowerShell

1. **Presiona** la tecla Windows + R
2. **Escribe** `powershell`
3. **Presiona** Enter

Verás una ventana azul (o negra) con texto blanco.

### Paso 2: Conectarse al Servidor AWS

1. **En PowerShell**, copia y pega este comando **COMPLETO**:

```powershell
ssh -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" ubuntu@44.193.3.170
```

2. **Presiona** Enter

3. **La primera vez**, verás un mensaje como:
```
The authenticity of host '44.193.3.170' can't be established.
Are you sure you want to continue connecting (yes/no)?
```

4. **Escribe** `yes` y presiona Enter

5. **Deberías ver** algo como:
```
Welcome to Ubuntu 24.04.3 LTS
ubuntu@ip-172-26-0-138:~$
```

✅ **Si ves `ubuntu@ip-...`:** ¡Estás conectado! El prompt ahora es verde/azul.
❌ **Si ves un error:** Verifica que:
   - El archivo `.pem` está en `C:\Users\caxul\.ssh\`
   - Copiaste el comando completo
   - Tu internet funciona

**IMPORTANTE:** Todo lo que escribas ahora se ejecuta en el servidor AWS, NO en tu computadora.

---

## 🔧 PARTE 4: CONFIGURAR EL SERVIDOR (15-20 minutos)

### Paso 1: Transferir Script de Instalación

**ABRE UNA NUEVA VENTANA DE POWERSHELL** (deja la otra abierta):

1. **Presiona** Windows + R
2. **Escribe** `powershell`
3. **Presiona** Enter

Ahora tienes 2 ventanas:
- **Ventana 1:** Conectada al servidor AWS (dice `ubuntu@ip-...`)
- **Ventana 2:** En tu computadora (dice `PS C:\Users\caxul>`)

### Paso 2: Transferir Archivos de Configuración

**EN LA VENTANA 2** (tu computadora), copia y pega:

```powershell
scp -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\setup-server.sh" ubuntu@44.193.3.170:~/
```

Presiona Enter. Deberías ver:
```
setup-server.sh                         100%  1234     50.2KB/s   00:00
```

Ahora transfiere el otro script:

```powershell
scp -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\start-app.sh" ubuntu@44.193.3.170:~/
```

### Paso 3: Ejecutar Script de Instalación

**CAMBIA A LA VENTANA 1** (la que está conectada al servidor).

1. **Copia y pega** este comando:
```bash
chmod +x setup-server.sh
```
Presiona Enter.

2. **Copia y pega** este comando:
```bash
./setup-server.sh
```
Presiona Enter.

3. **ESTO TARDARÁ 5-10 MINUTOS**. Verás mucho texto pasando. Es normal.

Verás cosas como:
```
[1/8] Actualizando sistema...
[2/8] Instalando dependencias...
[3/8] Agregando Docker GPG key...
...
```

4. **Cuando termine**, verás:
```
✅ Instalación completada exitosamente
⚠️  IMPORTANTE: Debes cerrar sesión y volver a conectarte
```

5. **Escribe**:
```bash
exit
```
Presiona Enter. La conexión se cerrará.

### Paso 4: Reconectar al Servidor

**EN LA VENTANA 1**, vuelve a conectar:

```powershell
ssh -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" ubuntu@44.193.3.170
```

### Paso 5: Verificar Docker

```bash
docker ps
```

Deberías ver:
```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
```

✅ **Si ves la tabla** (aunque esté vacía): Perfecto
❌ **Si dice "permission denied"**: Escribe `exit`, reconecta y vuelve a intentar

---

## 📦 PARTE 5: TRANSFERIR LA APLICACIÓN (10-15 minutos)

### Paso 1: Transferir el Archivo Comprimido

**EN LA VENTANA 2** (tu computadora), copia y pega este comando **COMPLETO**:

```powershell
scp -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" "C:\Users\caxul\Builds Laboratorio del Dolor\TimeTracker\timetracker.tar.gz" ubuntu@44.193.3.170:~/timetracker/
```

Presiona Enter.

**ESTO TARDARÁ 5-10 MINUTOS** dependiendo de tu internet.

Verás una barra de progreso:
```
timetracker.tar.gz           45% |*****     | 6.8MB   1.2MB/s  00:05 ETA
```

Cuando termine verás:
```
timetracker.tar.gz          100% |**********| 15.2MB  1.2MB/s  00:00
```

### Paso 2: Extraer Archivos en el Servidor

**CAMBIA A LA VENTANA 1** (servidor AWS).

1. **Copia y pega**:
```bash
cd ~/timetracker
```

2. **Copia y pega**:
```bash
tar -xzf timetracker.tar.gz
```
**Esto tardará 2-3 minutos**.

3. **Cuando termine**, verifica:
```bash
ls -la
```

Deberías ver carpetas como:
```
drwxr-xr-x  backend
drwxr-xr-x  frontend
drwxr-xr-x  docker
-rw-r--r--  docker-compose.yml
...
```

4. **Limpia el archivo comprimido**:
```bash
rm timetracker.tar.gz
```

---

## 🔐 PARTE 6: CONFIGURAR VARIABLES DE ENTORNO (5 minutos)

### Paso 1: Generar JWT Secret

**EN LA VENTANA 1** (servidor), copia y pega:

```bash
openssl rand -hex 32
```

Verás algo como:
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0
```

**COPIA ESTE TEXTO** (selecciónalo con el mouse y presiona Ctrl+Shift+C)

### Paso 2: Crear .env del Backend

1. **Copia y pega** este comando **COMPLETO**:

```bash
cat > ~/timetracker/backend/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:postgres@time-tracker-postgres:5432/time_tracker
JWT_SECRET=PONER_AQUI_LA_CLAVE_QUE_COPIASTE
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=https://timetracker.shaemarcus.com,http://timetracker.shaemarcus.com
REDIS_URL=redis://time-tracker-redis:6379
ENVIRONMENT=production
DEBUG=False
EOF
```

2. **ANTES de presionar Enter**, reemplaza `PONER_AQUI_LA_CLAVE_QUE_COPIASTE` con el texto que copiaste en el Paso 1

3. **Presiona** Enter

4. **Verifica** que se creó:
```bash
cat ~/timetracker/backend/.env
```

Deberías ver todas las variables. **Verifica que JWT_SECRET NO diga "PONER_AQUI..."**

### Paso 3: Crear .env del Frontend

**Copia y pega** este comando:

```bash
cat > ~/timetracker/frontend/.env.production << 'EOF'
VITE_API_URL=https://timetracker.shaemarcus.com/api
EOF
```

Presiona Enter.

---

## 🏗️ PARTE 7: CONSTRUIR E INICIAR LA APLICACIÓN (15-20 minutos)

### Paso 1: Dar Permisos al Script

```bash
chmod +x ~/start-app.sh
```

### Paso 2: Ejecutar Script de Inicio

```bash
cd ~/timetracker
```

```bash
~/start-app.sh
```

**ESTO TARDARÁ 10-15 MINUTOS**. Verás:

```
[1/5] Construyendo imagen del backend...
```

Mucho texto pasará. Es normal. Cuando veas:
```
✅ ¡Aplicación iniciada exitosamente!
```

**¡FELICIDADES! La aplicación está corriendo!**

---

## ✅ PARTE 8: VERIFICAR QUE FUNCIONA (5 minutos)

### Paso 1: Verificar en el Servidor

**EN LA VENTANA 1**, copia y pega:

```bash
curl http://localhost:8080/health
```

Deberías ver:
```json
{"status":"healthy"}
```

### Paso 2: Verificar desde tu Computadora

**Abre tu navegador** (Chrome, Firefox, etc.)

**Ve a:** http://44.193.3.170

Deberías ver la página de login de TimeTracker.

**Intenta iniciar sesión:**
- Email: `admin@timetracker.com`
- Password: `admin123`

✅ **Si entras:** ¡PERFECTO! La aplicación funciona
❌ **Si no carga:** Lee la sección de "Problemas Comunes" al final

---

## 🔥 PARTE 9: CONFIGURAR FIREWALL EN AWS (5 minutos)

### Paso 1: Ir a AWS Lightsail

1. **Abre** tu navegador
2. **Ve a:** https://lightsail.aws.amazon.com
3. **Inicia sesión** si te lo pide
4. **Busca** tu instancia `n8n-main-server`
5. **Haz clic** en el nombre de la instancia

### Paso 2: Configurar Reglas de Firewall

1. **Haz clic** en la pestaña "Networking" (arriba)
2. **Scroll hacia abajo** hasta ver "IPv4 Firewall"
3. **Verifica** que existan estas reglas:

| Application | Protocol | Port | From |
|-------------|----------|------|------|
| SSH | TCP | 22 | 0.0.0.0/0 |
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |

**Si falta alguna:**

4. **Haz clic** en "+ Add rule"
5. **Selecciona** el tipo (HTTP, HTTPS, etc.)
6. **Deja** "Restrict to IP address" en "Any"
7. **Haz clic** en "Create"

### Paso 3: Agregar Puerto Personalizado para Backend

1. **Haz clic** en "+ Add rule"
2. **Selecciona** "Custom"
3. **En Protocol:** deja "TCP"
4. **En Port:** escribe `8080`
5. **En Restrict to IP address:** deja "Any"
6. **Haz clic** en "Create"

---

## 🎉 ¡LISTO! LA APLICACIÓN ESTÁ EN LÍNEA

### Puedes acceder a:

**Por IP (funciona ahora):**
- Frontend: http://44.193.3.170
- Backend: http://44.193.3.170:8080/health

**Por dominio (después de que se propague el DNS):**
- http://timetracker.shaemarcus.com

### Credenciales:
- **Admin:** admin@timetracker.com / admin123
- **Usuario 1:** john@example.com / password123
- **Usuario 2:** jane@example.com / password123
- **Usuario 3:** bob@example.com / password123

---

## 🚨 PROBLEMAS COMUNES

### "No puedo conectarme por SSH"

**Síntomas:** Sale error al ejecutar `ssh -i ...`

**Soluciones:**
1. Verifica que el archivo `.pem` esté en `C:\Users\caxul\.ssh\`
2. Verifica que copiaste el comando completo
3. Intenta con este comando alternativo:
   ```powershell
   ssh -i "C:\Users\caxul\.ssh\LightsailDefaultKey-us-east-1.pem" -o "IdentitiesOnly=yes" ubuntu@44.193.3.170
   ```

### "La página no carga en el navegador"

**Síntomas:** Al abrir http://44.193.3.170 sale "No se puede acceder"

**Soluciones:**
1. Verifica que los contenedores estén corriendo:
   ```bash
   docker ps
   ```
   Deberías ver 4 contenedores.

2. Si no ves 4 contenedores:
   ```bash
   cd ~/timetracker
   docker compose up -d
   ```

3. Verifica firewall en AWS (Parte 9)

### "El DNS no resuelve"

**Síntomas:** `nslookup timetracker.shaemarcus.com` no muestra la IP

**Soluciones:**
1. Espera 30-60 minutos más
2. Verifica en tu proveedor de DNS que guardaste correctamente
3. Prueba con: http://44.193.3.170 mientras tanto

### "Error al transferir archivos"

**Síntomas:** `scp` da error "Connection refused" o similar

**Soluciones:**
1. Verifica tu conexión a internet
2. Verifica que el servidor esté encendido en AWS
3. Intenta reconectar por SSH primero

---

## 📞 SIGUIENTE PASO

**Una vez que todo funcione con la IP, el siguiente paso será:**

1. Esperar a que el DNS se propague completamente
2. Verificar que http://timetracker.shaemarcus.com funcione
3. Configurar Caddy para SSL/TLS (HTTPS)

**Esto lo haremos en la siguiente sesión.**

---

## 📊 COMANDOS ÚTILES PARA DESPUÉS

### Ver logs de la aplicación:
```bash
cd ~/timetracker
docker compose logs -f
```
(Presiona Ctrl+C para salir)

### Reiniciar la aplicación:
```bash
cd ~/timetracker
docker compose restart
```

### Detener la aplicación:
```bash
cd ~/timetracker
docker compose down
```

### Iniciar la aplicación:
```bash
cd ~/timetracker
docker compose up -d
```

### Ver estado de contenedores:
```bash
docker ps
```

---

**¿Listo para empezar? ¡Comienza por la PARTE 1!** 🚀
