Presencia Online (Sistema de Estado)
Ahora mismo tienes amigos, pero no sabes si están conectados o no.

El reto backend: Usar el notifications WebSocket (al que todos se conectan al hacer login) para llevar un registro de quién está online.

Qué implica: Cuando el "Usuario A" se conecta al WebSocket, el backend busca a sus amigos en la base de datos y les envía un evento {"type": "friend_online", "username": "Usuario A"}. Cuando se desconecta, envía un friend_offline.

--------

Matchmaking Basado en ELO (Emparejamiento Justo)
Ahora mismo tienes un "Lobby" donde cualquiera puede unirse a la sala de cualquiera.

El reto backend: Crear un endpoint POST /api/games/find_match que ponga al usuario en una "cola" (Queue). El backend debe buscar a otro jugador en la cola cuyo ELO sea similar (ej: +/- 50 puntos) y, si lo encuentra, crear una sala privada para ellos y enviarles el game_id a ambos para que entren.

---------

Sistema de Replays (Guardar los Movimientos)
El reto backend: En lugar de guardar solo el resultado final en la base de datos (Ganó Blanco, 30-34), guardar la secuencia exacta de movimientos (ej: ["e6", "f4", "c3"...]).

Qué implica: Añadir una columna en la tabla game_history de tipo JSON. Crear un endpoint GET /api/games/history/{match_id}/replay que devuelva esa lista para que (en el futuro) el frontend pueda reproducir la partida paso a paso.

---------

Automatizacion Continua (CI/CD)
Ya tienes una herramienta increíble: run_all.py. El siguiente paso profesional es no tener que ejecutarlo tú a mano.

Que falta: Configurar GitHub Actions (o GitLab CI).

Como hacerlo: Crear un archivo .github/workflows/test.yml que levante una base de datos de prueba en Docker, instale las dependencias de FastAPI y ejecute python test_scripts/run_all.py cada vez que alguien haga un push o un Pull Request. Si un test falla, no se permite fusionar el código.


---------


El dilema de las "Fichas Zombi"
¿Qué pasa con las fichas de un jugador cuando pulsa el botón de "Rendirse" o se le desconecta el internet?

Tu lógica actual: Las fichas se quedan en el tablero y mantienen su color original. Los otros 3 jugadores pueden seguir utilizándolas para hacer flanqueos y robárselas.

¿Es un problema?: No, es una variante muy válida (hace que el jugador que se rinde sea una "mina de oro" para los demás). Pero algunos juegos de mesa optan por convertir esas fichas en "muros grises" que ya no se pueden voltear ni usar para flanquear. Es solo una decisión de diseño que debes tener clara.


---------

Opciones de partida personalizadas
Actualmente la creación de salas es muy directa (1v1 o 1v1v1v1). En el futuro, a los jugadores les suele gustar personalizar la sala "básica":

Elegir si la sala es Pública o Privada (con contraseña).

Elegir el tiempo de turno (ej. Partida Rápida de 1 minuto vs Partida Lenta de 10 minutos).

Opcional: Elegir el tamaño del tablero en 4P (ej. jugar en 12x12 en lugar de 16x16 para que la partida sea más caótica y rápida).


---------

Gestión de Conexiones Muertas (Ping/Pong o Heartbeats)
Actualmente confías en que la librería websockets lance una excepción si el cliente se desconecta (por ejemplo, cuando cierra la pestaña).

El problema: Si un usuario pierde la conexión en el móvil (entra en un túnel, pierde el 4G), el socket a veces se queda "medio abierto" (estado half-open). El servidor piensa que el usuario sigue ahí y nunca dispara el temporizador de abandono de 30 segundos.

La mejora técnica: Implementar un sistema de Ping/Pong en ws/manager.py. El servidor debe enviar un mensaje invisible {"type": "ping"} cada 10 segundos. Si el cliente no responde con un {"type": "pong"} en 5 segundos, el servidor cierra activamente el socket y dispara el abandono.


---------


⚠️ Un "Pero" global que debemos apuntar para el futuro
Aunque place_free está perfecta, revisando cómo funciona me he dado cuenta de un detalle importante a nivel global (del motor del juego) que afectará a casi todas las habilidades, especialmente a esta. Te lo dejo apuntado para que lo tengamos en mente, no hace falta que lo arreglemos hoy:

El problema del salto de turno automático: En el Reversi clásico, si te toca jugar pero no tienes ningún movimiento válido que voltee fichas, pierdes el turno automáticamente.

Si tu sistema (en resolve_game_state o _next_piece_with_moves_4p) salta automáticamente a un jugador cuando tiene 0 movimientos válidos, le estás quitando la oportunidad de usar sus habilidades. Imagina que un jugador está bloqueado, pero tiene un place_free o una bomb en el inventario; debería poder usar su turno para lanzar la habilidad y salvarse, en lugar de que el juego le salte el turno instantáneamente.


---------