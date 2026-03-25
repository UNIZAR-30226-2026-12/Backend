# Documentación de Tests

## `test_user_social.py`
*Gestión de identidad, perfil y relaciones sociales.*

* **Bloque 1: Autenticación, perfil y personalización:** Valida el ciclo de identidad completo (registro, login, validación de credenciales), consulta y edición de perfil, personalización de elementos visuales (tablero/fichas), acceso a estadísticas y protección de rutas sin autenticar.
* **Bloque 2: Sistema de amigos:** Comprueba el flujo de relaciones interpersonales, incluyendo envío y aceptación de solicitudes, actualización de las listas de amigos, rechazo de solicitudes duplicadas y eliminación de contactos.
* **Bloque 3: Leaderboard global:** Verifica la existencia, formato y estructura de datos del ranking global, asegurando su correcto orden descendente basado en el ELO de los usuarios.

## `test_matchmaking.py`
*Creación de partidas y comunicación en sala.*

* **Bloque 1: Lobby público y gestión de salas:** Evalúa el alta de salas públicas, su visibilidad y desaparición en el lobby, la correcta unión de los jugadores y la validación de errores (intentos de acceso a salas llenas o inexistentes).
* **Bloque 2: Flujo de invitación amistosa (duelos):** Simula el ciclo completo de partidas privadas mediante WebSocket. Cubre el envío de invitaciones, recepción de notificaciones en tiempo real, aceptación del duelo y conexión final a la sala de juego.
* **Bloque 3: Chat bidireccional en partida:** Verifica la entrega bidireccional y en tiempo real de la mensajería, comprobando la exactitud del remitente, la integridad del contenido y la gestión de mensajes vacíos.

## `test_game_logic.py`
*Motor de juego, reglas, sincronización y persistencia.*

* **Bloque 1: Partida contra la IA:** Valida el flujo del modo `vs_ai`, incluyendo la asignación inicial, confirmación de movimientos del jugador, respuesta automatizada de la inteligencia artificial y la correcta transición de turnos.
* **Bloque 2: Sincronización del tablero entre dos jugadores:** Asegura la consistencia del estado de la partida en el modelo 1v1. Verifica la sincronización del tablero inicial, el broadcast de cada movimiento, la actualización del campo `last_move` y la rotación del turno.
* **Bloque 3: Reglas de juego y seguridad:** Prueba la robustez del motor ante acciones no permitidas: movimientos fuera de turno, desplazamientos a casillas prohibidas u ocupadas, y la inyección de payloads malformados (fuzzing).
* **Bloque 4: Fin de partida y persistencia:** Evalúa el flujo de finalización mediante rendición, comprobando la correcta declaración del ganador, la variación y actualización del ELO en la base de datos, y el registro exacto en el historial de ambos jugadores.

## `test_resilience.py`
*Estabilidad de red, reconexiones y aislamiento.*

* **Bloque 1: Intermitencia agresiva (flickering):** Mide la respuesta del sistema ante desconexiones repetidas y rápidas, asegurando que no se corrompe el estado de la partida, que se aceptan los movimientos posteriores y que no se disparan abandonos erróneos.
* **Bloque 2: Reconexión exitosa tras microcorte:** Verifica que un usuario puede recuperar su sesión, asignación de color y estado general tras una pérdida de conexión inferior a 1 segundo, sin que el servidor notifique un fin de partida al rival.
* **Bloque 3: Abandono definitivo por timeout:** Comprueba la lógica de finalización cuando un jugador pierde la conexión sin rendirse. Valida la activación del temporizador y la declaración del ganador por incomparecencia (W/O).
* **Bloque 4: Aislamiento total de salas:** Garantiza la estanqueidad de las sesiones evaluando múltiples partidas concurrentes. Asegura que los eventos de WebSocket se emiten exclusivamente a los participantes de la sala correspondiente, evitando cualquier fuga de datos transversal.