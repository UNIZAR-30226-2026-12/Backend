# Propuesta de Endpoints para el Backend de Random Reversi

A continuación se detalla una propuesta arquitectónica y de API (REST/WebSockets) para dar vida al juego. El backend será el encargado de manejar la lógica del juego (Reversi), la base de datos (PostgreSQL), la seguridad y la concurrencia entre jugadores.

## 1. Autenticación y Usuarios (`/api/auth` y `/api/users`)
Gestión del ciclo de vida de las cuentas, perfiles e inicio de sesión.
*   `POST /api/auth/register`: Crea un nuevo usuario. Deberá hashear la contraseña antes de guardarla en PostgreSQL.
*   `POST /api/auth/login`: Verifica credenciales y devuelve un token de sesión (ej. JWT).
*   `GET  /api/users/me`: Devuelve los datos del usuario autenticado (username, ELO, estadísticas, avatar, colores preferidos).
*   `PUT  /api/users/me`: Actualiza las preferencias e información básica del usuario.
*   `PUT  /api/users/customization`: Actualiza la configuración de estilo del usuario (avatar elegido, tableros y fichas preferidas).
*   `POST /api/users/avatar`: Permite subir una imagen con formato multipart-form data.
*   `GET  /api/users/:userId/stats`: Consulta las estadísticas de un usuario en específico.
*   `GET  /api/users/me/history`: Historial de partidas del jugador, mostrando si ganó, perdió o empató, y la fluctuación de ELO.

## 2. Sistema Social y Amigos (`/api/friends`)
Permite invitar y listar a otros jugadores.
*   `GET  /api/friends`: Lista todos los amigos, solicitudes pendientes y peticiones de juego a la vez (o se puede desglosar).
*   `POST /api/friends/request`: Envía una solicitud de amistad a otro jugador mediante su `username`.
*   `POST /api/friends/:userId/accept`: Acepta una solicitud recibida.
*   `POST /api/friends/:userId/reject`: Rechaza una solicitud de amistad enviada hacia nosotros.
*   `DELETE /api/friends/:userId`: Elimina a un amigo de nuestra lista de amigos.
*   `POST /api/games/invite`: Invita a un amigo a unirse a una partida (1vs1 o 1vs1vs1vs1).

## 3. Emparejamiento y Salas (Matchmaking) (`/api/lobbies` y `/api/games`)
Para jugar online, los jugadores deben encontrar partidas públicas o crear cerradas.
*   `GET  /api/games/public`: Lista las salas públicas actuales esperando jugadores (status: 'waiting'), mostrando número de plaza (ej: 2/4), creador y ELO.
*   `POST /api/games`: Crea una nueva sala de partida (1vs1 o 1vs1vs1vs1), devolviendo un ID de sala (`gameId`).
*   `POST /api/games/:gameId/join`: Inscribe a un jugador secundario a la sala de juego y notifica para su inicio.

## 4. Clasificación e Historial (`/api/leaderboard`)
*   `GET /api/leaderboard`: Devuelve el ranking global (Top N jugadores) ordenado por **ELO actual**. Puede incluir filtros (mensual, amigos, global).

## 5. Partida en Curso y Lógica del Juego (WebSockets)
> [!IMPORTANT]
> Para la jugabilidad en tiempo real y mecánicas especiales con **Habilidades** (bombas, cambio de polaridad de fichas, alteración de turnos), **REST no es suficiente**. Es esencial conectar cada juego vía un Endpoint de **WebSocket** (`ws://dominio/api/games/:gameId/ws`) que fluya la información al instante.

### Mensajes (Topics) del WebSocket
*   **`room_sync`**: Sincroniza y presenta a la sala quiénes se han unido antes de empezar.
*   **`game_state_update`**: El servidor envía la matriz de fichas, de quién es el turno, turnos saltados (`skipTurns`) y listas de habilidades pendientes por usar.
*   **`player_move`**: El cliente notifica al servidor "El jugador A se mueve a {row: X, col: Y}". El servidor valida y si es correcto emite el nuevo tablero a todos.
*   **`use_ability`**: Mensaje clave donde un jugador usa una habilidad especial (`bomb`, `skip_rival_turn`, etc.). El servidor evalúa las consecuencias geográficas en el tablero y reemite hacia todos los clientes lo ocurrido.
*   **`player_resign`**: Un usuario notifica que se da de baja intencional. El servidor ajusta la balanza de ELO.

### El Motor de Reglas en Backend (Cálculos de Movimientos)
El servidor es la verdadera fuente de la verdad para evitar trampas:
1.  **Validación de turno**: Verificar si el mensaje que llega y su firma corresponden al que le toca.
2.  **Cálculo de Flanqueo (Flanking)**: En Reversi, colocar una ficha debe "encerrar" fichas enemigas en vertical, horizontal o diagonal para voltearlas.
3.  **Mecanismo de Items y Puntería**: Muchas fichas ("?") dan habilidades. El servidor es quien otorga una aleatoria (de entre las 15) al pisarlas.
4.  **Condición de Fin**: El servidor evalúa cuándo finalizan los movimientos o recursos, dando el fallo ELO final.

## 6. Jugador vs IA Offline/Red Local
Puesto que en el frontend el usuario puede elegir jugar "Contra la IA", tienes dos opciones:
*   **A) Lógica en Frontend:** El cliente resuelve el algoritmo "Minimax" en Javascript localmente (no necesita consultar al servidor para mover, ideal si no guarda estadísticas en BBDD).
*   **B) IA Server-Side:** Un bot gestionado por el servidor detecta que se juega "contra máquina" y se auto-asigna el turno generando sus respuestas "minimax" y devolviéndolas por WebSocket como otro cliente más.

---
> [!TIP]
> **Base de Datos (Transaccional)**
> PostgreSQL funcionará perfectamente. Las tablas actuales de `users`, `friendships`, `lobbies`, `games` (estado general, modo, ganadores y ELO) y `moves` proveen un marco inicial sólido que solo requería pequeñas ampliaciones (como `invited_id` en `lobbies`).
