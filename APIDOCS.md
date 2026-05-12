# 🎮 Reversi AI - API Documentation

## 📋 Tabla de Contenidos
- [Setup](#setup)
- [🔐 Autenticación](#autenticación)
- [Endpoints REST](#endpoints-rest)
  - [🔐 Auth](#auth-apiauth)
  - [👤 Users & Avatar](#users--avatar-apiusers)
  - [🤝 Friends](#friends-apifriends)
  - [🎮 Games & Lobby](#games--lobby-apigames)
  - [🏆 Ranking](#ranking-apiranking)
- [⚡ WebSockets](#websockets)

---

## Setup

**URL Base:** `http://localhost:8000/api` (ajustar según entorno dev/prod)

**Header requerido en todos los requests (excepto los marcados como públicos):**
```http
Authorization: Bearer <tu_token>
Content-Type: application/json
```

---

## 🔐 Autenticación

**Manejo de Errores Común:**
- `401 Unauthorized` → `token` inválido, faltante o expirado → Se requiere un nuevo login.
- `400 Bad Request` → Errores de validación o lógica del negocio → Leer el atributo `detail` adjunto.
- `404 Not Found` → Recurso o usuario inexistente.
- `403 Forbidden` → Permisos insuficientes (Ej. intentar chatear con alguien que no es amigo).

---

## Endpoints REST

### 🔐 AUTH (`/api/auth`)

#### 🔵 POST `/api/auth/register` *(Público)*
**Crear un nuevo usuario.** Asigna un ELO base de 1000 por defecto.

**Body requerido:**
```json
{
  "username": "string (requerido, único)",
  "email": "string (requerido, formato válido, único)",
  "password": "string (requerido, min 6 chars)"
}
```

**Respuesta (200):**
```json
{
  "id": 1,
  "username": "user123",
  "email": "user@mail.com",
  "elo": 1000,
  "avatar_url": null,
  "preferred_piece_color": "black",
  "preferred_board_color": "green"
}
```

---

#### 🔵 POST `/api/auth/login` *(Público)*
**Iniciar sesión y obtener el token JWT**

**Body requerido (Form-Data `application/x-www-form-urlencoded`):**
```text
username=user123 (o el email)
password=MiClaveSecreta 
```

**Respuesta (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "token_type": "bearer"
}
```

---

#### 🔵 POST `/api/auth/forgot-password` *(Público)*
**Generar una nueva contraseña aleatoria y enviarla al email del usuario.**

Flujo interno:
1. Busca el usuario por email (case-insensitive).
2. Si no existe, devuelve 200 igualmente (no revela si el email está registrado).
3. Si existe: genera contraseña aleatoria de 8 caracteres (mayúsculas + minúsculas + dígitos + símbolos `!@#$%&*-_+=?`), la hashea, **actualiza la BD primero** y **después** envía el correo en texto plano con la nueva contraseña.

> El orden (BD antes que correo) garantiza que si falla el envío, la contraseña antigua quede invalidada y el usuario pueda reintentar sin quedar bloqueado con credenciales contradictorias.

**Body requerido:**
```json
{
  "email": "user@mail.com"
}
```

**Respuesta (200):**
```json
{
  "message": "Si el correo existe, recibirás una nueva contraseña"
}
```

**Errores:**
- `500` → Fallo al enviar el correo (la contraseña ya fue actualizada en BD).

---

### 👤 USERS & AVATAR (`/api/users`)

#### 🟢 GET `/api/users/me`
**Obtener los datos principales del perfil en sesión**

**Respuesta (200):**
```json
{
  "id": 1,
  "username": "user123",
  "email": "user@mail.com",
  "elo": 1050,
  "avatar_url": "https://...",
  "preferred_piece_color": "black",
  "preferred_board_color": "green"
}
```

---

#### 🟠 PUT `/api/users/me`
**Actualizar datos primarios.** Pide confirmación de contraseña en caso de modificar email/username.

**Body requerido (campos opcionales):**
```json
{
  "username": "user124",
  "email": "new@mail.com",
  "current_password": "OldPassword123",
  "new_password": "NewPassword124"
}
```

**Respuesta (200):**
```json
{
  "id": 1,
  "username": "user124",
  "email": "new@mail.com",
  "elo": 1050,
  "avatar_url": "https://...",
  "preferred_piece_color": "black",
  "preferred_board_color": "green"
}
```

---

#### 🟠 PUT `/api/users/customization`
**Actualizar personalización estética (sólo URIs, o colores preferidos)**

**Body (campos opcionales):**
```json
{
  "avatar_url": "string",
  "preferred_piece_color": "white",
  "preferred_board_color": "blue"
}
```

**Respuesta (200):**
```json
{
  "id": 1,
  "username": "user124",
  "email": "new@mail.com",
  "elo": 1050,
  "avatar_url": "https://NUEVA_URL",
  "preferred_piece_color": "white",
  "preferred_board_color": "blue"
}
```

---

#### 🔵 POST `/api/users/avatar`
**Subir un nuevo avatar como archivo binario.** La imagen se almacena directamente en la base de datos codificada en `base64`, sin escritura en disco. Al eliminar la cuenta, el avatar desaparece automáticamente.

**Formatos aceptados:** `image/png`, `image/jpeg`, `image/webp`, `image/gif` — Tamaño máximo: **2 MB**

**Body requerido (Multipart/form-data):**
- Archivo binario adjunto bajo la key `file`.

**Respuesta (200):**
```json
{
  "avatar_url": "data:image/png;base64,iVBORw0KGgo..."
}
```

> [!NOTE]
> El valor devuelto en `avatar_url` es una **data URL** estándar, utilizable directamente como `src` en etiquetas `<img>` sin ninguna petición adicional al servidor.


#### 🟠 PUT `/api/users/me/elo`
**Actualizar el ELO y Peak ELO (Internal/Game usage)**
El servidor actualiza automáticamente el `peak_elo` utilizando la función `GREATEST`, asegurando que el máximo histórico nunca disminuya.

**Body requerido:**
```json
{
  "elo": 1100
}
```

**Respuesta (200):**
```json
{
  "id": 1,
  "username": "user124",
  "email": "new@mail.com",
  "elo": 1100,
  "avatar_url": "https://...",
  "preferred_piece_color": "white",
  "preferred_board_color": "blue"
}
```

---

#### 🟢 GET `/api/users/me/stats`
*(Lo mismo aplica a **GET** `/api/users/{user_id}/stats`)*
**Obtener estadísticas propias del usuario (Partidas, winrate, rachas, némesis, detalles 4p).**

**Respuesta (200):**
```json
{
  "username": "user123",
  "elo": 1050,
  "avatar_url": "https://...",
  "total_games": 55,
  "wins": 30,
  "losses": 20,
  "draws": 5,
  "winrate": 54.5,
  "peak_elo": 1100,
  "win_streak": 3,
  "winrate_black": 60.0,
  "winrate_white": 48.2,
  "nemesis_name": "RivalSupremo",
  "nemesis_losses": 4,
  "victim_name": "NoobMaster",
  "victim_wins": 5,
  "stats_1v1": {
    "total_games": 50,
    "wins": 28,
    "losses": 17,
    "draws": 5,
    "winrate": 56.0
  },
  "stats_4p": {
    "total_games": 5,
    "wins": 2,
    "losses": 3,
    "win_streak": 1,
    "first_place": 2,
    "second_place": 1,
    "third_place": 1,
    "fourth_place": 1
  }
}
```

---

#### 🟢 GET `/api/users/{user_id}/h2h`
**Estadísticas directas (Cara a Cara) actuales contra el amigo/objetivo indicado.**

**Respuesta (200):**
```json
{
  "total_matches": 10,
  "wins": 4,
  "losses": 5,
  "draws": 1,
  "total_matches_4p": 2,
  "first_places_4p": 1,
  "other_places_4p": 1
}
```

---

#### 🔵 POST `/api/users/me/history`
**Añadir registro histórico de un juego concluido.**

**Body requerido:**
```json
{
  "opponent_name": "RivalX",
  "result": "Ganada | Perdida | Empate | 1º | 2º...",
  "score": "40",
  "rankChange": "15",
  "mode": "1vs1",
  "player_color": "black"
}
```

**Respuesta (200):**
```json
{
  "id": 142,
  "date": "2024-03-15",
  "opponent_name": "RivalX",
  "mode": "1vs1",
  "result": "Ganada",
  "score": "40",
  "rankChange": "15",
  "player_color": "black"
}
```

---

#### 🟢 GET `/api/users/me/history`
*(Lo mismo aplica a **GET** `/api/users/{user_id}/history`)*
**Obtiene una lista de objetos GameHistoryResponse ordenada por `created_at DESC`.**

**Query params opcionales:**
- `limit`: cantidad de registros a devolver. Valor por defecto: `10`. Máximo: `100`.
- `mode`: filtra por modo si se necesita una vista específica (`1vs1`, `1vs1vs1vs1`, `vs_ai`, y sus variantes compatibles).

> [!TIP]
> Para el preview de la sala de espera conviene pedir solo las partidas más recientes con `limit=5` y no filtrar por modo en cliente.

**Respuesta (200):**
```json
[
  {
    "id": 142,
    "date": "2024-03-15",
    "opponent_name": "RivalX",
    "mode": "1vs1",
    "result": "Ganada",
    "score": 40,
    "rankChange": 15,
    "player_color": "black"
  }
]
```

---

#### 🔴 DELETE `/api/users/me`
**Eliminación permanente irreversible de la cuenta propia del usuario.**

**Respuesta (200):**
```json
{
  "status": "success",
  "message": "Usuario user123 y todos sus datos han sido eliminados"
}
```

---

### 🤝 FRIENDS (`/api/friends`)

#### 🟢 GET `/api/friends`
**Panel principal social: Tus amigos offline/online, solicitudes entrantes y retos (invitaciones a salas).**

El campo `status` de cada amigo se calcula en backend usando la conexión activa al canal de notificaciones (`/ws/notifications`) y, si existe, también la conexión de partida (`/ws/play/{game_id}`).

**Respuesta (200):**
```json
{
  "online": [
     { "id": 2, "name": "Pedro", "rr": 1200, "avatar_url": "...", "unread_count": 0, "status": "online" }
  ],
  "offline": [
     { "id": 3, "name": "Marta", "rr": 1150, "avatar_url": "...", "unread_count": 0, "status": "offline" }
  ],
  "requests": [
     { "id": 5, "name": "Maria", "rr": 1000, "avatar_url": "..." }
  ],
  "gameRequests": [
     { "id": 8, "name": "Invitador_XYZ", "rr": 1050, "avatar_url": "...", "gameMode": "1vs1", "lobby_id": 14 }
  ],
  "pausedGames": [
     {
       "game_id": 124,
       "mode": "1vs1",
       "participants": ["Juan", "Pedro"],
       "paused_by": ["Juan"],
       "active_players": ["Juan", "Pedro"]
     }
  ]
}
```

---

#### 🔵 POST `/api/friends/request`
**Añadir a alguien por nombre exacto.**

> [!CAUTION]
> **Límite de Seguridad:** Si un usuario rechaza tu solicitud **3 veces**, el sistema bloqueará futuros intentos de envío hacia ese usuario para prevenir el acoso (HTTP 403).

**Body requerido:**
```json
{
  "username": "Maria"
}
```

**Respuesta (200):**
```json
{
  "message": "Solicitud enviada"
}
```

---

#### 🔵 POST `/api/friends/{user_id}/accept`
*(También aplica para* `/api/friends/{user_id}/reject` *y* `🔴 DELETE /api/friends/{user_id}`*)*
**Interacciones de cambio de estado a una petición o borrar amigo existente.**

**Respuesta (200):**
```json
{
  "message": "Solicitud aceptada"
}
```

> En `reject` y `DELETE` la respuesta real es `{"message": "Solicitud/Amigo eliminado"}`.

---

#### 🟢 GET `/api/friends/{user_id}/chat`
**Historial de mensajes con tu amigo.**

**Respuesta (200):**
```json
{
  "messages": [
    {
       "id": 1,
       "sender_id": 1,
       "sender_name": "Juan",
       "receiver_id": 2,
       "receiver_name": "Pedro",
       "message": "Ggwp",
       "is_read": true,
       "created_at": "2024-03-15T10:30:00Z"
    }
  ]
}
```

---

#### 🔵 POST `/api/friends/{user_id}/chat`
**Enviar un nuevo mensaje de texto privado.**

**Body requerido:**
```json
{
  "message": "Hola, ¿jugamos?"
}
```

**Respuesta (200):**
```json
{
  "message": {
    "id": 2,
    "sender_id": 1,
    "receiver_id": 2,
    "message": "Hola, ¿jugamos?",
    "is_read": false,
    "created_at": "..."
  }
}
```

---

#### 🔵 POST `/api/friends/{user_id}/chat/read`
**Marcar todos los mensajes con ese usuario como leídos.**

**Respuesta (200):**
```json
{
  "message": "Mensajes marcados como leídos"
}
```

---

### 🏆 RANKING (`/api/ranking`)

#### 🟢 GET `/api/ranking/`
**Ranking global de jugadores.** Por defecto devuelve el Top 50.

**Query Parameters (opcionales):**
- `limit`: int (1-100, default 50).
- `skip`: int (offset, default 0).

**Respuesta (200):**
```json
{
  "ranking": [
    {
      "id": 45,
      "username": "Kratos",
      "elo": 2040,
      "avatar_url": "..."
    }
  ]
}
```

---

### 🎮 GAMES & LOBBY (`/api/games`)

#### 🔵 POST `/api/games/create`
**Crea un Lobby público (Matchmaking general).**

**Body requerido:**
```json
{
  "mode": "1vs1" | "1v1" | "1vs1vs1vs1" | "1v1v1v1" | "vs_ai" | "1vs1_skills" | "1v1_skills" | "1vs1vs1vs1_skills" | "1v1v1v1_skills" | "vs_ai_skills"
}
```

**Respuesta (200):**
```json
{
  "game_id": "123",
  "creator": "Juan",
  "mode": "1vs1"
}
```

---

#### 🟢 GET `/api/games/public`
**Devuelve todos los lobbies no iniciados y públicos.**

**Respuesta (200):**
```json
{
  "lobbies": [
    {
      "game_id": "123",
      "creator": "Juan",
      "avatar_url": "...",
      "creator_rr": 1050,
      "mode": "1v1v1v1",
      "players": 2,
      "max_players": 4,
      "status": "waiting"
    }
  ]
}
```

---

#### 🔵 POST `/api/games/join/{game_id}`
**Unirte al lobby público de otra persona.**

**Respuesta (200):**
```json
{
  "status": "success",
  "game_id": "123"
}
```

---

#### 🔵 POST `/api/games/invite`
**Crea lobby privado e inyecta push ws al amigo para invitarlo de inmediato.**

**Número esperado de invitaciones:** 1 para `1vs1`/`1v1`, 3 para `1vs1vs1vs1`/`1v1v1v1`.

**Body requerido:**
```json
{
  "friend_ids": [2],
  "mode": "1vs1" | "1v1" | "1vs1vs1vs1" | "1v1v1v1" | "1vs1_skills" | "1v1_skills" | "1vs1vs1vs1_skills" | "1v1v1v1_skills"
}
```

**Respuesta (200):**
```json
{
  "game_id": "124",
  "creator": "TuUsername",
  "mode": "1vs1",
  "invites_sent": 1
}
```

---

#### 🔵 POST `/api/games/{game_id}/accept`
*(También aplica a `/reject`)*
**Responder al reto popup in-game.**

**Respuesta (200):**
```json
{
  "status": "success",
  "game_id": "124"
}
```

---

#### 🔵 POST `/api/games/{game_id}/leave`
**Abandonar lobby de espera o rendirse si la partida ha empezado.**

**Respuesta (200):**
```json
{
  "status": "success",
  "message": "Has abandonado la sala"
}
```

---

#### 🔵 POST `/api/games/{game_id}/ready`
**Marcar al jugador como 'Listo' o 'No Listo' en la sala de espera.**

**Body requerido:**
```json
{
  "ready": true
}
```

**Respuesta (200):**
```json
{
  "status": "success",
  "ready": true,
  "game_status": "waiting"
}
```

---

#### 🔴 POST `/api/games/{game_id}/kick/{username}`
**Expulsar a un jugador del lobby (Sólo el creador de la sala).**

**Respuesta (200):**
```json
{
  "status": "success",
  "message": "Player expulsado"
}
```

---

#### 🤖 POST `/api/games/{game_id}/add_bot`
**Añadir un bot (IA) al lobby para rellenar un hueco (Sólo el creador de la sala).**

**Respuesta (200):**
```json
{
  "status": "success",
  "bot_name": "IA_1"
}
```

---

#### 🟢 GET `/api/games/{game_id}/state`
**Obtener información pre-match sobre los miembros, si aceptaron y su estado 'Listo'.**

> Este endpoint reporta `status` como `waiting` o `playing`; cuando la partida ya terminó, la implementación actual normaliza el estado a `playing` mientras la sala sigue viva en memoria.

**Respuesta (200):**
```json
{
  "game_id": "124",
  "status": "waiting | playing",
  "mode": "1vs1",
  "players": [
     {
       "id": 1,
       "username": "Player1",
       "rr": 1000,
       "avatar_url": "...",
       "is_ready": true
     },
     {
       "id": -1,
       "username": "IA_1",
       "rr": 1000,
       "avatar_url": "",
       "is_ready": true
     }
  ]
}
```

---

## ⚡ WebSockets

Como los `WebSockets` estándar no envían cabeceras de autorización custom fácilmente, se usa `Query Parameters`: `?token=...`

### A. Canal de Notificaciones Globales
`ws://host:port/ws/notifications?token={tu_token}`
- Este canal mantiene la presencia online del usuario mientras navega por la app.
- `duel_invite`: Tu amigo creó un lobby con `/api/games/invite` y te toca a ti.
- `invite_response`: Tu amigo ya respondió.

### B. Canal de Partida Activa
`ws://host:port/ws/play/{game_id}?token={tu_token}`

#### 📤 Acciones del Cliente (JSON):
- `{"action": "set_ready", "ready": true|false}`: Indicar que estás listo en el lobby.
- `{"action": "make_move", "row": 0, "col": 0}`: Realizar un movimiento en el tablero.
- `{"action": "chat", "message": "Hola!"}`: Enviar un mensaje de chat (Limitado a **280 caracteres**. Soporta sanitización `XSS` automática).
- `{"action": "use_skill", "type": "bomb|gravity|fix_piece|..."}`: Usar una habilidad del inventario del jugador (puede requerir `row`/`col`/`target_player`/`direction` según la habilidad).
- `{"action": "pause"}`: Pausar/Despausar la partida (Solo disponible en partidas privadas con amigos).
- `{"action": "surrender"}`: Rendirse o abandonar la partida en curso.

> [!IMPORTANT]
> **Restricciones de Seguridad Críticas:**
> - **Rate Limiting:** Se permite un máximo de 1 mensaje (cualquier acción) cada **0.5 segundos** por cliente para prevenir ataques de denegación de servicio o spam.
> - **Tipado Estricto:** Las coordenadas `row` y `col` deben ser estrictamente números enteros (`int`). El envío de tipos incorrectos provocará el cierre de la conexión por el servidor.
> - **Dimensiones del Tablero:** El servidor valida que las coordenadas estén dentro de **8x8** (1v1) o **16x16** (4P).

> [!TIP]
> **Optimización de Rendimiento (AI):**
> El motor de la `IA` se ejecuta en hilos secundarios mediante `asyncio.to_thread`. Esto garantiza que el `Event Loop` del servidor nunca se bloquee, manteniendo la latencia mínima incluso en tableros de `16x16`. En modos con `_skills`, la IA también puede consumir habilidades automáticamente cuando tenga opciones válidas en inventario.

#### 📥 Mensajes del Servidor (JSON):
- `{"type": "room_sync", "payload": {...}}`: Sincronización de los jugadores en el lobby (`RR`, avatares, estado listo).
- `{"type": "player_assignment", "payload": {"color": "black|white|red|blue"}}`: Asigna tu color/pieza al conectar.
- `{"type": "waiting_for_player", "payload": {"message": "..."}}`: Mensaje informativo de espera de jugadores.
- `{"type": "game_state_update", "payload": {...}}`: Estado completo del tablero y la partida.
  - Incluye `paused_usernames`: Lista de usuarios que han pausado la partida.
  - Al detectar `game_over: true`, el servidor programa la **limpieza automática** de la sala en memoria tras 5 segundos.
- `{"type": "chat_message", "payload": {"sender": "User", "message": "..."}}`: Nuevo mensaje de chat recibido.
- `{"type": "error", "payload": {"message": "..."}}`: Notificación de error (movimiento inválido, etc).
- `{"type": "invite_response", "payload": {"action": "accepted|rejected|room_closed|left|kicked", ...}}`: Notificación de respuesta a invitación o cierre de sala.
