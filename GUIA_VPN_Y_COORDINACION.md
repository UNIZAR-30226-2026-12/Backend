# Guía de Conexión y Acceso - Equipo de Desarrollo

Este documento detalla cómo conectaros a la red privada y acceder a los servicios desplegados.

## 1. Conexión VPN (WireGuard)
Para acceder a los servicios internos, es **obligatorio** estar conectado a la VPN.

### Instalación
1.  **Descargar Cliente**: [WireGuard Installation](https://www.wireguard.com/install/)
2.  **Configuración**: Os enviaré un archivo `.conf` personalizado a cada uno.
3.  **Importar**: Abrid WireGuard -> "Import tunnel(s) from file" -> Seleccionar el archivo `.conf`.
4.  **Activar**: Pulsad "Activate".

## 2. Servicios Desplegados
Una vez conectados a la VPN, podéis acceder a las siguientes URLs:

### 🛠️ Gestión
*   **Portainer (Gestión de Docker)**: [https://192.168.0.201:9443](https://192.168.0.201:9443)
    *   *Nota: Aceptad la advertencia de certificado de seguridad.*

### 🚀 Aplicación (Equipo Backend)
Estos servicios están desplegados por el equipo de Backend para pruebas iniciales:
*   **Frontend basico para probar el backend (Reversi)**: [http://192.168.0.201:8080](http://192.168.0.201:8080)
*   **Backend API**: [http://192.168.0.201:8081](http://192.168.0.201:8081)
    *   *Documentación API (Swagger)*: [http://192.168.0.201:8081/docs](http://192.168.0.201:8081/docs)

## 3. Instrucciones para el Equipo de Frontend
El equipo encargado del Frontend "Real" deberá desplegar su versión en este servidor. Ya lo coordinaremos más adelante

### Pasos para Desplegar Frontend
1.  Aseguraros de tener los archivos `Dockerfile` y `docker-compose.yml` en vuestro repositorio (ya preparados en la carpeta `frontend/`).
2.  Acceder a **Portainer** ([https://192.168.0.201:9443](https://192.168.0.201:9443)).
3.  Crear un nuevo **Stack** o actualizar el existente.
4.  Subir vuestro código o conectar vuestro repositorio.
5.  Coordinar con el equipo de Backend para asegurar que los puertos `8080` (Frontend) y `8081` (Backend) se mapean correctamente.
