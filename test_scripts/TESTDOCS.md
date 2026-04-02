# Documentación de Tests

## `test_user_social.py`
*Gestión de identidad, perfil y relaciones sociales.*

* **Bloque 1: Autenticación, perfil y personalización:** Valida el ciclo de identidad completo (registro, login, validación de credenciales), consulta y edición de perfil, personalización de elementos visuales (tablero/fichas), acceso a estadísticas y protección de rutas sin autenticar.
* **Bloque 2: Sistema de amigos:** Comprueba el flujo de relaciones interpersonales, incluyendo envío y aceptación de solicitudes, actualización de las listas de amigos, rechazo de solicitudes duplicadas y eliminación de contactos.
* **Bloque 3: Leaderboard global:** Verifica la existencia, formato y estructura de datos del ranking global, asegurando su correcto orden descendente basado en el ELO y validando el sistema de paginación (limit/skip).

## `test_matchmaking.py`
*Creación de partidas y comunicación en sala.*

* **Bloque 1: Lobby público y gestión de salas:** Evalúa el alta de salas públicas, su visibilidad y desaparición en el lobby, la correcta unión de los jugadores y la validación de errores (intentos de acceso a salas llenas o inexistentes).
* **Bloque 2: Flujo de invitación amistosa (duelos):** Simula el ciclo completo de partidas privadas mediante WebSocket. Cubre el envío de invitaciones, recepción de notificaciones en tiempo real, aceptación del duelo y conexión final a la sala de juego.
* **Bloque 3: Chat bidireccional en partida:** Verifica la entrega bidireccional y en tiempo real de la mensajería, comprobando la exactitud del remitente, la integridad del contenido y la gestión de mensajes vacíos.
* **Bloque 4: Matchmaking y Salas de Espera (4P):** Valida la creación de salas públicas de 4 jugadores, su persistencia en el lobby durante el llenado progresivo y el sistema de invitaciones múltiples a amigos.
* **Bloque 5: Sincronización y Chat (4P):** Asegura la asignación de 4 colores únicos, el handshake de preparación parcial (espera a 4/4 ready) y la propagación de mensajes en el chat grupal.
* **Bloque 6: Lobby Resiliente y Autoridad (Kick/Bots):** Evalúa la gestión de la sala por parte del Host: expulsión de jugadores (kick), rellenado automático de huecos con bots (IA) y persistencia de la sala tras abandonos de invitados.

## `test_game_logic.py`
*Motor de juego, reglas, sincronización y persistencia.*

* **Bloque 1: Partida contra la IA:** Valida el flujo del modo `vs_ai`, incluyendo la asignación inicial, confirmación de movimientos del jugador, respuesta automatizada de la inteligencia artificial y la correcta transición de turnos.
* **Bloque 2: Sincronización del tablero entre dos jugadores:** Asegura la consistencia del estado de la partida en el modelo 1v1. Verifica la sincronización del tablero inicial, el broadcast de cada movimiento, la actualización del campo `last_move` y la rotación del turno.
* **Bloque 3: Reglas de juego y seguridad:** Prueba la robustez del motor ante acciones no permitidas: movimientos fuera de turno, desplazamientos a casillas prohibidas u ocupadas, y la inyección de payloads malformados (fuzzing).
* **Bloque 4: Fin de partida y persistencia (1v1):** Evalúa el flujo de finalización mediante rendición, comprobando la declaración del ganador, la variación del ELO y el registro en el historial.
* **Bloque 5: Motor de Juego y Reglas (4P):** Test de unidad sobre el tablero 16x16, validando el flanqueo multicolor (captura de múltiples colores en una línea) y el salto automático de turno para jugadores sin movimientos.
* **Bloque 6: Fin de Partida, ELO y Estadísticas (4P):** Valida el cálculo de posiciones (1º a 4º), la distribución de ELO estilo "Battle Royale" y el registro del puesto obtenido en el historial del usuario.
* **Bloque 7: IA y Empates Matemáticos:** Verifica la heurística de la IA en tableros de 16x16 y la resolución justa de empates múltiples (asignación de la misma posición a jugadores con igual puntuación).

## `test_resilience.py`
*Estabilidad de red, reconexiones y aislamiento.*

* **Bloque 1: Intermitencia agresiva (flickering):** Mide la respuesta del sistema ante desconexiones repetidas y rápidas, asegurando que no se corrompe el estado de la partida.
* **Bloque 2: Reconexión exitosa tras microcorte:** Verifica que un usuario puede recuperar su sesión, asignación de color y estado general tras una pérdida de conexión inferior a 1 segundo.
* **Bloque 3: Abandono definitivo por timeout:** Comprueba la lógica de finalización cuando un jugador pierde la conexión sin rendirse. Valida la activación del temporizador y la victoria por incomparecencia.
* **Bloque 4: Aislamiento total de salas:** Garantiza la estanqueidad de las sesiones evaluando múltiples partidas concurrentes sin fuga de datos.
* **Bloque 5: Rendición y Abandono Parcial (4P):** Gestiona la salida de jugadores individuales en modo 4P, permitiendo que la partida continúe para el resto, y procesando el bloqueo mutuo si todos abandonan.
* **Bloque 6: Resiliencia de Red Flickering (4P):** Prueba la estabilidad ante reconexiones múltiples y simultáneas en el modo de 4 jugadores, manteniendo la persistencia de identidad y color.