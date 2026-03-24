# 🎮 Reversi AI - API Documentation

Este archivo resume el estado actual del backend (Marzo 2026) tras la refactorización modular y la implementación del motor multijugador en tiempo real.

> **⚠️ IMPORTANTE - AUTENTICACIÓN:** 
> Todos los endpoints REST (excepto Auth público) requieren el header: `Authorization: Bearer <tu_token>`
> Todos los WebSockets requieren el token como query parameter: `?token=<tu_token>`

---

## 🔐 1. Autenticación y Perfil de Usuario

| Método | Endpoint                    | Descripción                               | Request Payload Sugerido                               |
| :---   | :---                        | :---                                      | :---                                                   |
| **POST**| `/api/auth/register`        | Registro de nuevo usuario.               | `{"username": "...", "email": "...", "password": "..."}`|
| **POST**| `/api/auth/login`           | Inicio de sesión (devuelve JWT).         | Form Data: `username=...&password=...`                 |
| **GET** | `/api/users/me`             | Obtiene los datos del perfil actual.     | -                                                      |
| **PUT** | `/api/users/me`             | Actualiza username o email.              | `{"username": "...", "email": "..."}`                  |
| **PUT** | `/api/users/customization`  | Actualiza colores y avatar.              | `{"avatar_url": "...", "preferred_board_color": "green"}`|
| **POST**| `/api/users/avatar`         | Sube una imagen de avatar real.          | Archivo (Multipart/form-data)                          |

---

## 📊 2. Estadísticas, Historial y Ranking

| Método | Endpoint                    | Descripción                                      | Request Payload Sugerido |
| :---   | :---                        | :---                                             | :---                     |
| **GET** | `/api/ranking/`             | Obtiene el Top 50 global ordenado por ELO.       | -                        |
| **GET** | `/api/users/me/stats`       | Estadísticas propias (Winrate, Némesis, Rachas). | -                        |
| **GET** | `/api/users/{id}/stats`     | Estadísticas públicas de otro jugador.           | -                        |
| **GET** | `/api/users/me/history`     | Historial de las últimas 10 partidas jugadas.    | -                        |
| **GET** | `/api/users/{id}/h2h`       | Estadísticas Head-to-Head contra un amigo.       | -                        |

---

## 👥 3. Sistema Social (Amigos)

Gestión de la lista de amigos y solicitudes.

| Método | Endpoint                    | Descripción                                      | Request Payload Sugerido          |
| :---   | :---                        | :---                                             | :---                              |
| **GET** | `/api/friends`              | Lista de amigos y solicitudes pendientes.        | -                                 |
| **POST**| `/api/friends/request`      | Envía una solicitud de amistad.                  | `{"username": "nombre_amigo"}`    |
| **POST**| `/api/friends/{id}/accept`  | Acepta una solicitud entrante.                   | -                                 |
| **POST**| `/api/friends/{id}/reject`  | Rechaza una solicitud entrante.                  | -                                 |
| **DELETE**| `/api/friends/{id}`       | Elimina a un usuario de tu lista de amigos.      | -                                 |

---

## ⚔️ 4. Lobby y Gestión de Salas (Matchmaking)

Control de flujo REST antes de saltar al WebSocket de la partida.

| Método | Endpoint                    | Descripción                                      | Request Payload Sugerido       |
| :---   | :---                        | :---                                             | :---                           |
| **POST**| `/api/games/create`         | Crea una sala nueva. Modos: `"1v1"` o `"vs_ai"`.| `{"mode": "1v1"}`              |
| **GET** | `/api/games/public`         | Devuelve listado de salas públicas esperando rival.| -                              |
| **POST**| `/api/games/join/{game_id}` | El jugador 2 se une a una sala existente.        | -                              |
| **POST**| `/api/games/invite`         | Crea sala privada e invita a un amigo (Push).    | `{"friend_username": "..."}`   |

---

## ⚡ 5. WebSockets (Comunicación en Tiempo Real)

### A. Canal de Notificaciones Globales
*Mantener abierto siempre que el usuario esté logueado en la app.*
* **URL:** `ws://host:port/ws/notifications?token={tu_token}`
* **Eventos que emite el Servidor:**
  * `duel_invite`: Cuando un amigo usa `/api/games/invite` contra ti.
  * `friend_request`: Cuando alguien te envía una solicitud de amistad.

### B. Canal de Partida (In-Game)
*Abrir inmediatamente después de crear o unirse a una sala.*
* **URL:** `ws://host:port/ws/play/{game_id}?token={tu_token}`

#### 📥 Acciones del Cliente (Lo que Frontend envía al Servidor)
Formato siempre en JSON puro con la clave `action`.

| Acción | Payload Estructural | Descripción |
| :--- | :--- | :--- |
| **Mover Ficha** | `{"action": "make_move", "row": 2, "col": 3, "player": "black"}` | Intenta colocar una ficha. El backend valida si es legal. |
| **Chat** | `{"action": "chat", "message": "Hola rival"}` | Envía un mensaje de texto a la sala. |
| **Rendirse** | `{"action": "surrender", "player": "black"}` | Termina la partida al instante. El rival gana y se ajusta el ELO. |

#### 📤 Eventos del Servidor (Lo que Frontend recibe)
Formato estructurado con `type` y `payload`.

| Tipo de Evento (`type`) | Contenido del `payload` | Descripción |
| :--- | :--- | :--- |
| `player_assignment` | `{"color": "black"}` | Se envía nada más conectar para indicar tu bando. |
| `waiting_for_player`| `{"message": "..."}` | Indica que eres el jugador 1 y el rival aún no ha entrado. |
| `chat_message` | `{"sender": "UserX", "message": "Hola"}`| Un mensaje de texto recibido en la sala. |
| `game_state_update` | `{"board": [...], "current_player": "white", "score": {"black": 4, "white": 1}, "valid_moves": [...], "game_over": false, "winner": null}` | **El núcleo del juego.** Se recibe tras cada movimiento válido o al terminar la partida. Dibuja la UI en base a esto. |
| `error` | `{"message": "Movimiento inválido"}` | Se envía si intentas hacer algo ilegal o fuera de tu turno. |

---

## 🛑 6. Reglas de Desconexión y Abandono (Importante para UI)

El backend implementa protección contra microcortes y ragequits. El Frontend debe estar preparado para este flujo:

1. **Si un jugador cierra el WebSocket abruptamente:** La partida NO termina inmediatamente.
2. **Ventana de Reconexión:** El servidor abre un temporizador invisible de **30 segundos**. 
3. **Reconexión exitosa:** Si el jugador vuelve a abrir el WebSocket de la misma sala (`/ws/play/{game_id}`) antes de 30 segundos, el servidor le reenviará el `player_assignment` y el `game_state_update` actual para que siga jugando como si nada.
4. **Abandono Definitivo:** Si pasan 30 segundos, el servidor declara "Abandono". Enviará un último `game_state_update` con `game_over: true` y la victoria asignada al jugador que permaneció en la sala. El ELO se restará al jugador desconectado.