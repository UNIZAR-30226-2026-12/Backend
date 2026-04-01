# 🎮 Reversi AI - API Documentation

## 📋 Tabla de Contenidos
- [Setup](#setup)
- [Autenticación](#autenticación)
- [Endpoints REST](#endpoints-rest)
  - [Auth](#auth-apiauth)
  - [Users & Avatar](#users--avatar-apiusers)
  - [Friends](#friends-apifriends)
  - [Games & Lobby](#games--lobby-apigames)
  - [Ranking](#ranking-apiranking)
- [WebSockets](#websockets)

---

## Setup

**URL Base:** `http://localhost:8000/api` (ajustar según entorno dev/prod)

**Header requerido en todos los requests (excepto los marcados como públicos):**
```http
Authorization: Bearer <tu_token>
Content-Type: application/json
```

---

## Autenticación

**Manejo de Errores Común:**
- `401 Unauthorized` → Token inválido, faltante o expirado → Se requiere un nuevo login.
- `400 Bad Request` → Errores de validación o lógica del negocio → Leer el atributo `detail` adjunto.
- `404 Not Found` → Recurso o usuario inexistente.
- `403 Forbidden` → Permisos insuficientes (Ej. intentar chatear con alguien que no es amigo).

---

## Endpoints REST

### AUTH (`/api/auth`)

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
**Solicitar código de recuperación de contraseña al email**

**Body requerido:**
```json
{
  "email": "user@mail.com"
}
```

**Respuesta (200):**
```json
{
  "message": "Correo de recuperación enviado"
}
```

---

#### 🔵 POST `/api/auth/reset-password` *(Público)*
**Establecer nueva contraseña utilizando el código recibido al correo**

**Body requerido:**
```json
{
  "email": "user@mail.com",
  "code": "123456",
  "new_password": "NewPassword123"
}
```

**Respuesta (200):**
```json
{
  "message": "Contraseña restablecida correctamente"
}
```

---

### USERS & AVATAR (`/api/users`)

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
**Subir un nuevo avatar real como archivo binario**

**Body requerido (Multipart/form-data):**
- Archivo binario adjunto bajo la key `file`.

**Respuesta (200):**
```json
{
  "avatar_url": "/uploads/avatars/user123_abc.png"
}
```

---

#### 🟠 PUT `/api/users/me/elo`
**Actualizar el ELO y Peak ELO (Internal/Game usage)**

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
    "third_place": 1
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
  "score": 40,
  "rankChange": 15,
  "duration_seconds": 120,
  "game_mode": "1vs1",
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
  "score": 40,
  "rankChange": 15,
  "player_color": "black"
}
```

---

#### 🟢 GET `/api/users/me/history`
*(Lo mismo aplica a **GET** `/api/users/{user_id}/history`)*
**Obtiene una lista de objetos GameHistoryResponse con los últimos 10 juegos.**

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

### FRIENDS (`/api/friends`)

#### 🟢 GET `/api/friends`
**Panel principal social: Tus amigos offline/online, solicitudes entrantes y retos (invitaciones a salas).**

**Respuesta (200):**
```json
{
  "friends": [
     { "id": 2, "name": "Pedro", "rr": 1200, "avatar_url": "...", "unread_count": 0, "status": "online" }
  ],
  "requests": [
     { "id": 5, "name": "Maria", "rr": 1000, "avatar_url": "..." }
  ],
  "gameRequests": [
     { "id": 8, "name": "Invitador_XYZ", "rr": 1050, "avatar_url": "...", "gameMode": "1vs1", "lobby_id": 14 }
  ]
}
```

---

#### 🔵 POST `/api/friends/request`
**Añadir a alguien por nombre exacto.**

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
  "message": "Solicitud aceptada/rechazada/eliminada"
}
```

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

### GAMES & LOBBY (`/api/games`)

#### 🔵 POST `/api/games/create`
**Crea un Lobby público (Matchmaking general).**

**Body:**
```json
{
  "mode": "1vs1"
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
      "mode": "1vs1"
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

**Body:**
```json
{
  "friend_ids": [2],
  "mode": "1vs1"
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

#### 🟢 GET `/api/games/{game_id}/state`
**Obtener información pre-match sobre los miembros, si aceptaron y su estado 'Listo'.**

**Respuesta (200):**
```json
{
  "game_id": "124",
  "status": "waiting | playing | finished",
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
       "id": 2,
       "username": "Player2",
       "rr": 1200,
       "avatar_url": "...",
       "is_ready": false
     }
  ]
}
```

---

#### 🔵 POST `/api/games/{game_id}/ready`
**Marcarse como "Listo". Si el último dice Listos=true, inicia partida automáticamente.**

**Body:** 
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
  "game_status": "waiting | playing"
}
```

---

### RANKING (`/api/ranking`)

#### 🟢 GET `/api/ranking/`
**Devuelve el Top 50 Global Playerboard.**

**Respuesta (200):**
```json
{
  "ranking": [
    {
      "id": 45,
      "username": "Kratos",
      "elo": 2040,
      "avatar_url": "..."
    },
    {
      "id": 12,
      "username": "Atenea",
      "elo": 1900,
      "avatar_url": "..."
    }
  ]
}
```

---

## WebSockets

Como los WebSockets estándar no envían cabeceras de autorización custom fácilmente, se usa Query Parameters: `?token=...`

### A. Canal de Notificaciones Globales
`ws://host:port/ws/notifications?token={tu_token}`
- `duel_invite`: Tu amigo creó un lobby con `/api/games/invite` y te toca a ti.
- `invite_response`: Tu amigo ya respondió.

### B. Canal de Partida Activa
`ws://host:port/ws/play/{game_id}?token={tu_token}`
- Permite hacer `make_move`, `chat`, `surrender`.
- Devuelve Broadcasts constantes: `game_state_update` (el tablero completo JSON, dictando turnos y si perdiste o ganaste).