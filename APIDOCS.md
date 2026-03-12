# 🎮 Reversi AI - API Documentation

Este archivo resume el estado actual del backend (12 de Marzo 2026) tras la refactorización modular.

---

## 🔐 1. Autenticación y Usuarios

> **ℹ️ IMPORTANTE:** Todos los endpoints (excepto Login y Register) requieren el header:  
> `Authorization: Bearer <tu_token>`

| Método | Endpoint                     | Descripción                                     | Payload Sugerido                         |
| ------ | ---------------------------- | ----------------------------------------------- | ---------------------------------------- |
| POST   | `/api/auth/register`         | Registro de usuario                             | `{"username": "...", "password": "..."}` |
| POST   | `/api/auth/login`            | Login de usuario                                | `{"username": "...", "password": "..."}` |
| GET    | `/api/users/me`              | Obtener perfil propio                           | -                                        |
| PUT    | `/api/users/me`              | Actualiza username o email                      | `{"username": "...", "email": "..."}`    |
| PUT    | `/api/users/customization`   | Actualiza preferencias de interfaz (colores)    | `{"avatar_url": "..."}`                  |
| GET    | `/api/users/{id}/stats`      | Estadísticas (ELO, partidas ganadas/perdidas)   | -                                        |
| GET    | `/api/users/me/history`      | Historial de partidas terminadas                | -                                        |
| POST   | `/api/users/avatar`          | Sube una imagen de avatar (Multipart)           | Archivo Multipart                        |

---

## 👥 2. Sistema Social (Amigos y Retos)

Gestión de la lista de amigos y búsqueda de usuarios para duelos.

| Método | Endpoint                     | Descripción                                          |
| ------ | ---------------------------- | ---------------------------------------------------- |
| GET    | `/api/friends`               | Lista de amigos conectados y solicitudes pendientes. |
| POST   | `/api/friends/request`       | Enviar solicitud de amistad (`{"username": "..."}`). |
| POST   | `/api/friends/{id}/accept`   | Aceptar una solicitud de amistad.                    |
| POST   | `/api/friends/{id}/reject`   | Rechaza solicitud de amistad pendiente.              |
| DELETE | `/api/friends/{id}`          | Elimina a un amigo de la lista de amigos.            |

---

## 🎮 3. Lobby y Gestión de Duelos

Control de flujo antes de entrar a la partida.

### 🏠 Salas Públicas
- **`POST /api/games/create`**: Crea una sala que aparecerá en el listado global.
- **`GET /api/games/public`**: Devuelve un array de objetos tipo `{"game_id": "...", "creator": "..."}`.

### ⚔️ Duelos Directos (Privados)
- **`POST /api/games/invite`**: Crea una sala privada y envía una notificación al amigo.
  - **Request**: `{"friend_username": "d"}`
  - **Response**: `{"game_id": "UUID", "status": "sent"}`

- **`POST /api/games/invite/accept`**: El invitado confirma la entrada.
  - **Request**: `{"friend_username": "a"}`
  - **Response**: `{"status": "success", "game_id": "UUID"}`

- **`POST /api/games/invite/reject`**: El invitado rechaza. Se borra la sala y se notifica al creador.
  - **Request**: `{"friend_username": "a"}`

---

## ⚡ WebSockets (Comunicación en Vivo)

### A. Notificaciones Globales

**URL:** `ws://host:port/ws/notifications/{username}`

**Propósito:** Mantener al usuario "online" y recibir invitaciones de duelo.

**Evento Recibido (`duel_invite`)**

```json
{
  "type": "duel_invite",
  "payload": {
    "creator": "username_retador",
    "game_id": "UUID-1234",
    "message": "¡username_retador te ha retado a un duelo!"
  }
}
```

---

### B. Sala de Juego

**URL:** `ws://host:port/ws/play/{game_id}`

**Propósito:** Sincronización del tablero y validación de movimientos.

**1. Al conectar (Asignación)**  
El servidor responde inmediatamente con el color asignado al usuario.
```json
{ 
  "type": "player_assignment", 
  "payload": { "color": "black" } 
}
```

**2. Durante la partida (`game_state_update`)**  
Se envía cada vez que el estado cambia (movimientos, conexiones).
```json
{
  "type": "game_state_update",
  "payload": {
    "board": [
      ["", "", ""],
      ["", "black", "white"]
    ],
    "current_player": "white",
    "score": {"black": 4, "white": 1},
    "valid_moves": [{"row": 2, "col": 2}],
    "game_over": false
  }
}
```

**3. Realizar Movimiento (Cliente -> Servidor)**
```json
{
  "action": "make_move",
  "row": 2,
  "col": 3,
  "player": "black"
}
```

**4. Errores y Rechazos**  
Si el rival rechaza el duelo mientras el creador de la sala inicial aún está esperando:
```json
{ 
  "type": "invite_rejected", 
  "payload": { "message": "El jugador rival ha rechazado el duelo." } 
}
```