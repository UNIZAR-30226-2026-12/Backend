1. Autenticación y Usuarios (/api/auth y /api/users)
Gestión del ciclo de vida de las cuentas, perfiles e inicio de sesión. Las rutas REST (excepto login/register) requieren la cabecera HTTP Authorization: Bearer <token>.

POST /api/auth/register: Crea un nuevo usuario. Hashea la contraseña antes de guardarla en PostgreSQL e inicializa el ELO a 1000.

POST /api/auth/login: Verifica credenciales (username y password) y devuelve un token de sesión JWT (access_token).

GET  /api/users/me: Devuelve los datos del usuario autenticado (username, email, ELO, avatar, colores preferidos).

PUT  /api/users/me: Actualiza la información básica del usuario (username, email).

PUT  /api/users/customization: Actualiza la configuración de estilo del usuario (avatar elegido, color de tablero y fichas).

POST /api/users/avatar: Permite subir una imagen con formato multipart/form-data y devuelve la URL pública.

GET  /api/users/{userId}/stats: Consulta las estadísticas de un usuario en específico (ELO, partidas totales, victorias).

PUT  /api/users/me/elo: Actualiza el ELO del jugador de forma segura tras una partida.

POST /api/users/me/history: Registra una partida finalizada en el historial del jugador.

GET  /api/users/me/history: Devuelve el historial de partidas del jugador ordenado por fecha.

2. Sistema Social y Amigos (/api/friends)
Permite gestionar la red de contactos del jugador.

GET  /api/friends: Lista 1) Amigos confirmados, 2) Solicitudes pendientes de aceptar, y 3) Invitaciones a juegos en curso.

POST /api/friends/request: Envía una solicitud de amistad a otro jugador mediante su username (incluye límite de bloqueos por rechazos múltiples).

POST /api/friends/{userId}/accept: Acepta una solicitud recibida.

POST /api/friends/{userId}/reject: Rechaza una solicitud de amistad (aumentando el contador de rechazos).

DELETE /api/friends/{userId}: Elimina a un amigo de nuestra lista o cancela una relación existente.

3. Emparejamiento y Salas (Matchmaking) (/api/games)
Gestión de partidas públicas y el sistema de Retos Privados directos.

Salas Públicas
POST /api/games/create: Crea una nueva sala pública online (status: 'waiting'). Inicializa el tablero en la RAM del servidor y devuelve el game_id.

GET  /api/games/public: Lista las salas públicas actuales esperando jugadores. (Incluye resiliencia: si el servidor reinicia, reconstruye el tablero en RAM).

POST /api/games/join/{game_id}: El Jugador 2 se une a una sala pública existente. La base de datos bloquea concurrentemente el acceso a un tercer jugador y marca la sala como 'playing'.

Retos Privados (Notificaciones Push)
POST /api/games/invite?target_username={user}: Crea una sala privada (solo en base de datos) y envía el desafío al instante por WebSocket.

POST /api/games/{game_id}/accept: El amigo acepta el desafío. Activa el tablero en la RAM y envía un aviso por WS al retador original para que se una.

POST /api/games/{game_id}/reject: El amigo rechaza el desafío. Borra la sala pendiente de la BD y notifica al creador.

4. Clasificación e Historial (/api/leaderboard)
GET /api/leaderboard: Devuelve el ranking global (Top N jugadores) ordenado por ELO actual. Puede incluir filtros (mensual, amigos, global). (Implementación pendiente)

5. Canales de Tiempo Real (WebSockets)
[!IMPORTANT]
Seguridad por URL: Como los WebSockets no soportan cabeceras de autorización nativas, ambos endpoints requieren enviar el token en la URL: ?token={jwt}. Si es inválido, el servidor cerrará la conexión con el código HTTP 1008.

A) El Canal Global (/ws/notifications)
WS /ws/notifications?token={jwt}: Debe conectarse nada más abrir la App. Mantiene un mapeo 1:1 en el servidor.

Recibe: duel_invite (Aparece el Pop-up de desafío).

Recibe: invite_response (Avisa de si el rival aceptó o rechazó tu desafío).

B) La Partida en Curso (/ws/play/{game_id})
WS /ws/play/{game_id}?token={jwt}: Canal de alta frecuencia para la jugabilidad.

player_assignment (Server->Client): Asigna color (black/white).

waiting_for_player (Server->Client): Mensaje de espera para el creador.

game_state_update (Server->Client, Broadcast): Envía a ambos el estado completo (tablero, turno, movimientos válidos, puntuación y estado de la partida).

make_move (Client->Server): Petición JSON: {"action": "make_move", "row": X, "col": Y, "player": "black"}.

error (Server->Client, Unicast): Avisa si el movimiento fue inválido, ilegal o fuera de turno (solo lo ve el infractor).

6. Motor de Reglas en Backend (Cálculos de Movimientos)
El servidor es la verdadera fuente de la verdad para evitar trampas.

RAM vs Base de Datos: Para evitar lag, las partidas activas viven en un diccionario en la memoria RAM del servidor. Solo se toca PostgreSQL al iniciar o finalizar.

Validación de turno: Verificar si el mensaje que llega corresponde al que le toca y que la partida no ha acabado.

Cálculo de Flanqueo (Flanking): En Reversi, el servidor valida el movimiento y se encarga de voltear las fichas en vertical, horizontal o diagonal.

(Futuro) Mecanismo de Items y Habilidades: El servidor otorgará los efectos especiales (bombas, saltos de turno) y reemitirá el estado alterado a todos.

7. Jugador vs IA Offline/Red Local
Puesto que en el frontend el usuario puede elegir jugar "Contra la IA", tienes dos opciones:

A) Lógica en Frontend: El cliente resuelve el algoritmo "Minimax" en Javascript localmente (no necesita consultar al servidor para mover, ideal si no guarda estadísticas en BBDD).

B) IA Server-Side: Un bot gestionado por el servidor detecta que se juega "contra máquina" y se auto-asigna el turno generando sus respuestas "minimax" y devolviéndolas por WebSocket como otro cliente más.

[!TIP]
Base de Datos (Transaccional)
PostgreSQL funciona perfectamente. Las tablas actuales de users, friendships, lobbies (con el estado 'waiting' o 'playing'), games y game_history proveen un marco robusto y ya testeado para soportar miles de partidas concurrentes.