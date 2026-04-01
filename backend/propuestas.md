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
# COSAS QUE FALTAN DEL 4P

Fragilidad del Lobby (La sala "de cristal")
En 1v1: Si invitas a un amigo y le da a "Rechazar", o entra a la sala de espera y le da a "Salir", el servidor borra la sala (DELETE FROM lobbies). Esto tiene sentido, porque si tu único rival se va, te quedas solo.

El problema en 4P: Si el Anfitrión (Host) invita a 3 amigos, y uno solo de ellos le da a "Rechazar" la invitación (o entra y luego sale), ¡tu código actual ejecuta el mismo DELETE FROM lobbies! Destruye la sala entera y expulsa al Host y a los otros 2 amigos que ya estaban dentro y listos.

Lo que falta: En 4P, si alguien rechaza o sale de la fase waiting, simplemente debería vaciarse su hueco para que el Host pueda invitar a otra persona, sin destruir la sala entera.


---------


Injusticia Matemática en los Empates (Desempate por turno)
En 1v1: Si la partida acaba con empate a fichas (ej. 32 a 32), la función resolve_game_state devuelve winner: "draw". El ELO no se toca y a ambos se les registra un empate.

El problema en 4P: En tu función _compute_positions_4p, usas esto para desempatar: remaining.sort(key=lambda p: (-score.get(p, 0), TURN_ORDER_4P.index(p))).
Esto significa que si el Negro (Turno 0) y el Azul (Turno 3) empatan con 20 fichas cada uno, el Negro siempre quedará 1º y el Azul siempre quedará 2º por culpa de su orden de turno. En lugar de un "Empate por el 1º puesto", le das +50 de ELO al Negro y +25 de ELO al Azul injustamente.

Lo que falta: Que el 4P reconozca los empates a puntos y reparta el mismo puesto y el mismo ELO a los que empaten.


---------


La Inteligencia Artificial (vs_ai y Relleno de Huecos)
En 1v1: Si no tienes amigos conectados o no quieres jugar con randoms, puedes seleccionar el modo vs_ai y el servidor asigna a "IA" como jugador blanco.

El problema en 4P: El modo 4P exige estrictamente 4 humanos (participant_count_expected = 4). Si estáis 3 amigos en Discord, literalmente no podéis iniciar la partida. Estáis obligados a abrir la sala y esperar a que un desconocido entre.

Lo que falta: Poder lanzar una sala 4P con 3 humanos y rellenar el último hueco con 1 IA, o 1 humano contra 3 IAs.


---------


Falta de autoridad del Host (El Troll de la Sala)
En 1v1: Si abres una sala pública, entra un random y no le da al botón de "Listo" (set_ready: true), simplemente te vas de tu sala, se destruye y creas otra. Tardas 2 segundos.

El problema en 4P: Si estáis 3 amigos en la sala y dejáis el cuarto hueco abierto al público, si entra un random y decide no darle al botón de "Listo" para molestar, os tiene secuestrados a los tres. Como el juego no arranca hasta que los 4 digan "Ready", la única solución es destruir la sala y que los 3 amigos volváis a empezar el proceso de matchmaking.

Lo que falta: Un endpoint para que el creador de la sala (creator_id) pueda expulsar (Kick) a un jugador específico de la sala de espera.