#!/bin/bash
# Script de configuración automática del servidor TimeTracker
# Este script instala Docker, Docker Compose y prepara el entorno

set -e  # Detener si hay algún error

echo "======================================"
echo "🚀 TimeTracker - Setup Automático"
echo "======================================"
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Actualizar sistema
echo -e "${YELLOW}[1/8] Actualizando sistema...${NC}"
sudo apt update
sudo apt upgrade -y

# 2. Instalar dependencias
echo -e "${YELLOW}[2/8] Instalando dependencias...${NC}"
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# 3. Agregar Docker GPG key
echo -e "${YELLOW}[3/8] Agregando Docker GPG key...${NC}"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 4. Agregar repositorio Docker
echo -e "${YELLOW}[4/8] Agregando repositorio Docker...${NC}"
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Instalar Docker
echo -e "${YELLOW}[5/8] Instalando Docker...${NC}"
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# 6. Agregar usuario al grupo docker
echo -e "${YELLOW}[6/8] Configurando permisos de Docker...${NC}"
sudo usermod -aG docker ubuntu

# 7. Instalar Docker Compose
echo -e "${YELLOW}[7/8] Instalando Docker Compose...${NC}"
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 8. Crear directorio del proyecto
echo -e "${YELLOW}[8/8] Creando directorio del proyecto...${NC}"
mkdir -p ~/timetracker
cd ~/timetracker

echo ""
echo -e "${GREEN}======================================"
echo "✅ Instalación completada exitosamente"
echo "======================================"
echo ""
echo "Versiones instaladas:"
docker --version
docker-compose --version
echo ""
echo "⚠️  IMPORTANTE: Debes cerrar sesión y volver a conectarte para que los cambios tengan efecto"
echo ""
echo "Después de reconectar, verifica con: docker ps"
echo ""
