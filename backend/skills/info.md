# Sistema de Habilidades - Reversi

## Tabla de Habilidades

| ID | Nombre | Descripción | Tipo |
|---|---|---|---|
| ✔️ gravity | Gravedad | Desplaza fichas en dirección elegida | Ofensivo |
| ✔️ bomb | Bomba 3x3 | Voltea fichas en área 3x3 | Ofensivo |
| ✔️ fix_piece | Ficha Fija | Coloca ficha permanente e inmune | Defensivo |
| ✔️ unfix_piece | Quitar Ficha Fija | Elimina ficha fija | Herramienta |
| ✔️ place_free | Ficha Libre | Coloca ficha sin captura | Ofensivo |
| ✔️ skip_rival | Saltar Turno | Omite turno siguiente | Control |
| ✔️ lose_turn | Perder Turno | Pierde turno actual y el siguiente | Negativo |
| ✔️ flip_rival | Voltear Ficha | Convierte ficha rival | Ofensivo |
| ✔️ swap_colors | Intercambio Color | Intercambia colores | Control |
| ✔️ steal_skill | Robar Habilidad | Roba skill aleatoria | Robo |
| ✔️ exchange_skill | Intercambiar Skill | Intercambia skill | Intercambio |
| ✔️ give_skill | Dar Habilidad | Regala skill voluntariamente | Cooperativo |

---

## Reglas Globales

- Las habilidades se obtienen al caer en casillas especiales (?) durante el juego
- Usar una habilidad consume el turno actual del jugador
- Penalización: -2 puntos por cada habilidad sin usar al finalizar
- Fichas Fijas: Inmunes a cambios de color y movimiento por gravedad

---

## Especificaciones por Habilidad

### Gravedad (gravity)

**Tipo:** Ofensivo | **Modos:** 1v1, 4P | **Target:** No | **Dirección:** Sí

El jugador elige dirección (arriba, abajo, izquierda, derecha) y todas las fichas no fijas se desplazan hasta chocar con el borde o con otra ficha.

**Notas:**

- No afecta a las fichas fijas (permanecen en su posición).
- Las casillas de interrogante (`?`) son **fijas**: no se desplazan con la gravedad.
- Las fichas sí pueden caer sobre una casilla de interrogante y "apilarse" encima. El interrogante permanece y podrá ser recogido en un turno posterior mediante un movimiento normal.

---

### Bomba 3x3 (bomb)

**Tipo:** Ofensivo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Voltea fichas en área 3x3 centrada en objetivo.

**Comportamiento:**

- 1v1: Fichas voltean al color contrario
- 4P: Se asignan al jugador con menos fichas (empate = aleatorio)

**Notas:** Las fichas fijas NO se voltean.

---

### Ficha Fija (fix_piece)

**Tipo:** Defensivo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Coloca ficha permanente e inmune a capturas. Solo puede cambiar de color si se usa flip_rival sobre ella.

---

### Quitar Ficha Fija (unfix_piece)

**Tipo:** Herramienta | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Elimina ficha fija del tablero.

**Restricción:** Solo se puede usar si existe al menos una ficha fija. Si no hay, pierde el turno sin efecto.

---

### Ficha Libre (place_free)

**Tipo:** Ofensivo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Coloca ficha en casilla vacía sin necesidad de captura.

---

### Saltar Turno (skip_rival)

**Tipo:** Control | **Modos:** 4P | **Target:** No | **Dirección:** No

Omite un turno completo del siguiente jugador en la rotación.

---

### Perder Turno (lose_turn)

**Tipo:** Negativo | **Modos:** 1v1, 4P | **Target:** No | **Dirección:** No

Al usarla, el jugador pierde el turno **actual** (por el propio uso de la habilidad) y además el **siguiente** turno queda bloqueado. Efecto neto: el rival juega dos turnos consecutivos.

Crea tensión estratégica cuando se recibe de un rival (vía `give_skill` o `exchange_skill`): el jugador debe elegir entre usarla y perder dos turnos, o no usarla y pagar la penalización de -2 pts al final.

---

### Voltear Ficha (flip_rival)

**Tipo:** Ofensivo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Convierte una ficha rival al color propio.

**Excepción:** Las fichas fijas solo cambian de color pero se mantienen fijas.

---

### Intercambio de Color (swap_colors)

**Tipo:** Control | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Usuario elige rival e intercambian colores todas las fichas en tablero.

**Nota:** Las fichas fijas NO cambian de color.

---

### Robar Habilidad (steal_skill)

**Tipo:** Robo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Roba una habilidad aleatoria del rival.

**Restricción:** Solo se puede usar si al menos un rival tiene habilidades.

---

### Intercambiar Habilidad (exchange_skill)

**Tipo:** Intercambio | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Usuario elige habilidad a dar y rival a intercambiar. Recibe skill aleatoria del rival.

**Restricción:** Usuario: mín. 2 habilidades | Rival: mín. 1 habilidad.

---

### Dar Habilidad (give_skill)

**Tipo:** Cooperativo | **Modos:** 1v1, 4P | **Target:** Sí | **Dirección:** No

Usuario regala voluntariamente una habilidad a rival elegido.

**Restricción:** Usuario debe tener mín. 2 habilidades.

---

## Matriz de Compatibilidad

| Habilidad | 1v1 | 4P | Target | Dirección |
|---|---|---|---|---|
| gravity | Sí | Sí | No | Sí |
| bomb | Sí | Sí | Sí | No |
| fix_piece | Sí | Sí | Sí | No |
| unfix_piece | Sí | Sí | Sí | No |
| place_free | Sí | Sí | Sí | No |
| skip_rival | No | Sí | No | No |
| lose_turn | Sí | Sí | No | No |
| flip_rival | Sí | Sí | Sí | No |
| swap_colors | Sí | Sí | Sí | No |
| steal_skill | Sí | Sí | Sí | No |
| exchange_skill | Sí | Sí | Sí | No |
| give_skill | Sí | Sí | Sí | No |
