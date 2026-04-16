# Sistema de Habilidades - Reversi

Este documento detalla las 12 habilidades disponibles en el juego y sus efectos.

| ID | Habilidad | Descripción |
| :--- | :--- | :--- |
| **gravity** | Gravedad | El jugador elige una dirección (arriba, abajo, izquierda, derecha) y todas las fichas (excepto las fijas) se desplazan en esa dirección hasta chocar con el borde u otra ficha. |
| **bomb** | Bomba 3x3 | El jugador selecciona una ficha objetivo y todas las fichas en el área de 3x3 centrada en ese punto (excepto fichas fijas) se voltean a su color. |
| **fix_piece** | Ficha Fija | Permite colocar una ficha en una casilla vacía que se vuelve permanente e inmune a volteos o desplazamientos por gravedad. |
| **unfix_piece** | Quitar Ficha Fija | Permite eliminar una ficha fija del tablero (propia o del rival), dejando la casilla vacía. |
| **place_free** | Ficha Libre | Permite colocar una ficha en cualquier casilla vacía del tablero, sin necesidad de realizar capturas. |
| **skip_rival** | Saltar Turno Rival | El siguiente turno del rival (o el siguiente jugador en modo 4) se omite. |
| **lose_turn** | Perder Turno | (Efecto negativo) El jugador actual pierde su siguiente turno. |
| **flip_rival** | Voltear Ficha Rival | El jugador selecciona una ficha del oponente y la convierte a su propio color. No funciona con fichas fijas. |
| **swap_colors** | Intercambio de Color | Selecciona un rival y todas las fichas en el tablero de ambos jugadores intercambian sus colores. |
| **steal_skill** | Robar Habilidad | Roba una habilidad aleatoria del inventario de un oponente seleccionado. |
| **exchange_skill** | Intercambiar Habilidad | Intercambia una de tus habilidades (aleatoria, que no sea esta misma) por una habilidad aleatoria de un oponente. |
| **give_skill** | Dar Habilidad | Regala una de tus habilidades (aleatoria, que no sea esta misma) a un oponente seleccionado. |

## Reglas Generales
- Las habilidades se obtienen al caer en casillas con **"?"**.
- Usar una habilidad consume el turno del jugador.
- Si una partida termina y el jugador tiene habilidades sin usar, se le restan **2 puntos** por cada una.
- Las **Fichas Fijas** son inmunes a cambios de color y movimiento por gravedad.
