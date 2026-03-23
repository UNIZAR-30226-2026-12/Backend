# Reversi (Othello) con IA Backend (Python)

Este proyecto es un juego de Reversi que utiliza un motor de Inteligencia Artificial (Minimax con Poda Alfa-Beta) ejecutado en un backend robusto de Python.

**NOTA CRÍTICA:** A diferencia de otras versiones, este frontend **no tiene lógica de juego local**. Requiere obligatoriamente que el servidor de Python esté activo para funcionar.

## Tecnologías

- **Frontend:** React, TypeScript, Tailwind CSS.
- **Backend:** Python 3.x, FastAPI, Uvicorn.
- **IA:** Algoritmo Minimax implementado en el lado del servidor.

## Cómo ejecutar el proyecto

### 1. Iniciar el Backend (Obligatorio)

Primero, debes ejecutar el servidor de Python. Asegúrate de tener las dependencias instaladas:

```bash
pip install fastapi uvicorn pydantic
```

Luego, inicia el servidor:

```bash
uvicorn backend:app --reload
```

El servidor debe estar corriendo en `http://localhost:8000`.

### 2. Iniciar el Frontend

En otra terminal, inicia la interfaz de usuario:

```bash
npm install
npm run dev
```

Abre `http://localhost:5173`. Si el backend está apagado, verás una pantalla de advertencia roja y el juego no permitirá realizar movimientos.

## Arquitectura

El flujo de juego es:
1. El usuario realiza un clic.
2. El frontend envía las coordenadas al endpoint `/movimiento`.
3. El backend valida el movimiento del jugador, aplica los flanqueos y ejecuta inmediatamente la mejor respuesta de la IA.
4. El backend devuelve el estado final del tablero tras ambos turnos.

## Actualizar una BD ya existente

Si tienes el proyecto corriendo desde antes del **23‑03‑2025** y **no quieres borrar los datos**, ejecuta estos dos `ALTER TABLE` una sola vez:

```bash
docker exec reversi_postgres psql -U reversi_user -d reversi_db -c \
  "ALTER TABLE users ADD COLUMN IF NOT EXISTS peak_elo INTEGER;
   UPDATE users SET peak_elo = elo WHERE peak_elo IS NULL;
   ALTER TABLE game_history ADD COLUMN IF NOT EXISTS player_color VARCHAR(10) NOT NULL DEFAULT 'black';"
```

> Los compañeros que levanten el proyecto desde cero con `docker-compose up` **no necesitan hacer nada**: el esquema ya incluye estas columnas en `bbdd/init.sql`.
