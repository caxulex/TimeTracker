#!/bin/bash
# Script de inicialización de la aplicación TimeTracker
# Ejecuta este script DESPUÉS de transferir los archivos del proyecto

set -e

echo "======================================"
echo "🚀 TimeTracker - Inicialización"
echo "======================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: No se encontró docker-compose.yml${NC}"
    echo "Asegúrate de estar en el directorio ~/timetracker"
    exit 1
fi

# 1. Construir imagen backend
echo -e "${YELLOW}[1/5] Construyendo imagen del backend...${NC}"
docker build -t timetracker-backend ./backend
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backend construido exitosamente${NC}"
else
    echo -e "${RED}❌ Error construyendo backend${NC}"
    exit 1
fi

# 2. Construir imagen frontend
echo -e "${YELLOW}[2/5] Construyendo imagen del frontend...${NC}"
docker build -t timetracker-frontend ./frontend
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend construido exitosamente${NC}"
else
    echo -e "${RED}❌ Error construyendo frontend${NC}"
    exit 1
fi

# 3. Iniciar contenedores
echo -e "${YELLOW}[3/5] Iniciando contenedores...${NC}"
docker compose up -d
sleep 10

# 4. Verificar contenedores
echo -e "${YELLOW}[4/5] Verificando contenedores...${NC}"
docker ps

# 5. Esperar a que PostgreSQL esté listo
echo -e "${YELLOW}[5/5] Esperando PostgreSQL (15 segundos)...${NC}"
sleep 15

# 6. Inicializar base de datos
echo -e "${YELLOW}[6/6] Inicializando base de datos...${NC}"
docker exec timetracker-backend python -m app.seed

echo ""
echo -e "${GREEN}======================================"
echo "✅ ¡Aplicación iniciada exitosamente!"
echo "======================================"
echo ""
echo "📊 Estado de los contenedores:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "🌐 URLs de acceso:"
echo "   Frontend: http://44.193.3.170"
echo "   Backend:  http://44.193.3.170:8080"
echo "   Health:   http://44.193.3.170:8080/health"
echo ""
echo "👤 Credenciales de acceso:"
echo "   Admin: admin@timetracker.com / admin123"
echo ""
echo "📝 Ver logs en tiempo real:"
echo "   docker compose logs -f"
echo ""
