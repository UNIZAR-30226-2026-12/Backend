# Propuesta de Endpoints para el Backend de Random Reversi

A continuación se detalla una propuesta arquitectónica y de API (REST/WebSockets) para dar vida al juego. El backend será el encargado de manejar la lógica del juego (Reversi), la base de datos (PostgreSQL), la seguridad y la concurrencia entre jugadores.

## 1. Autenticación y Usuarios (`/api/auth` y `/api/users`)
Gestión del ciclo de vida de las cuentas, perfiles e inicio de sesión.
*   `POST /api/auth/register`: Crea un nuevo usuario. Deberá hashear la contraseña antes de guardarla en PostgreSQL.
*   `POST /api/auth/login`: Verifica credenciales y devuelve un token de sesión (ej. JWT).
*   `GET  /api/users/me`: Devuelve los datos del usuario autenticado (username, ELO, estadísticas, avatar, colores preferidos).
*   `PUT  /api/users/me`: Actualiza las preferencias del usuario (avatar, colores de fichas y tablero).
*   `GET  /api/users/:userId/stats`: Consulta las estadísticas de un usuario en específico.

## 2. Sistema Social y Amigos (`/api/friends`)
Permite invitar y listar a otros jugadores.
*   `GET  /api/friends`: Lista todos los amigos aprobados del usuario en sesión.
*   `POST /api/friends/request`: Envía una solicitud de amistad a otro jugador mediante su `username` o `id`.
*   `GET  /api/friends/requests/pending`: Lista las peticiones pendientes de aceptar.
*   `PUT  /api/friends/requests/:requestId`: Acepta o rechaza una solicitud recibida.

## 3. Emparejamiento y Salas (Matchmaking) (`/api/lobbies`)
Para jugar online, los jugadores deben encontrar partidas públicas o crear cerradas.
*   `GET  /api/lobbies`: Lista las salas públicas actuales esperando jugadores (modo 1vs1 o 1vs1vs1vs1).
*   `POST /api/lobbies`: Crea una nueva sala. El usuario puede especificar si es pública o privada, y el modo de juego. Devuelve un ID único para la sala (y un código corto para invitar a amigos).
*   `POST /api/lobbies/:lobbyId/join`: Permite a un jugador unirse a una sala.

## 4. Clasificación e Historial (`/api/leaderboard` y `/api/games/history`)
*   `GET /api/leaderboard`: Devuelve el ranking global (Top N jugadores) ordenado por **ELO actual**. Puede incluir filtros (mensual, amigos, global).
*   `GET /api/games/history`: Retorna el historial de partidas del jugador, mostrando si ganó, perdió o empató, y cuántos puntos de ELO fluctuaron en cada combate (para pintar la tabla que se vio en el frontend).

## 5. Partida en Curso y Lógica del Juego (WebSockets o REST)
> [!IMPORTANT]
> Para la jugabilidad en tiempo real (online o en red local), aunque se puede usar HTTP (Long Polling), **la mejor práctica es usar WebSockets (ej. Socket.io, SignalR, o la API nativa de ws)** para que los movimientos se reflejen sin latencia. A nivel de base de datos se guarda el tablero inicial y cada movimiento (o persistiendo solo el estado actual tras cada turno).

### Flujo REST para Acciones de Partida (`/api/games`)
*   `GET  /api/games/:gameId`: Obtiene el estado actual: la matriz del tablero, a quién le toca mover, cronómetros y puntuación de fichas.
*   `POST /api/games/:gameId/move`: El jugador envía `{ "row": 3, "col": 4 }`. **El backend es responsable de validar el movimiento** (si es legal según reglas de Reversi y si da la vuelta a fichas rivales). Devolverá el nuevo estado de la matriz, o "400 Bad Request" si el movimiento es inválido.
*   `POST /api/games/:gameId/resign`: Rendirse intencionadamente antes de terminar la partida (calcula el perdedor de inmediato ajustando el ELO).

### El Motor de Reglas en Backend (Cálculos de Movimientos)
El servidor es la verdadera fuente de la verdad para evitar trampas:
1.  **Validación de turno**: Verificar si el token que hace la petición a `/move` corresponde al jugador que tiene el turno.
2.  **Cálculo de Flanqueo (Flanking)**: En Reversi, colocar una ficha debe "encerrar" fichas enemigas en vertical, horizontal o diagonal para voltearlas.
3.  **Movimientos Válidos Restantes**: El servidor debe calcular si el próximo jugador tiene casillas válidas para mover; si no, el turno "salta", y si nadie puede mover o el tablero se llena, calcular ganadores.

## 6. Jugador vs IA Offline/Red Local
Puesto que en el frontend el usuario puede elegir jugar "Contra la IA", tienes dos opciones:
*   **A) Lógica en Frontend:** El cliente resuelve el algoritmo "Minimax" en Javascript localmente (no necesita consultar al servidor para mover, ideal si no guarda estadísticas en BBDD).
*   **B) IA Server-Side:** La ruta `/api/games/ai/move` o la máquina de estados del servidor se encarga de que, cuando es el turno del bot, este calcule su tirada y emita un evento de WebSocket o permita ser consultado informando del resultado, calculando un bot centralizado en el backend.

---
> [!TIP]
> **Base de Datos (Transaccional)**
> PostgreSQL funcionaría perfectamente. Sugiero tablas para `users`, `friendships`, `games` (estado general, modo, ganadores y ELO en riesgo) y `moves` (guardando la secuencia de X,Y del tablero para reproducir repeticiones si se deseara en el futuro).
