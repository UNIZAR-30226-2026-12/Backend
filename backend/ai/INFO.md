# Módulo: AI (Inteligencia Artificial)

**Responsabilidad:**
Motor de decisiones para el bot del juego cuando se juega en modo "Contra la IA".

**Funcionalidades:**
- Implementación del algoritmo Minimax con poda Alfa-Beta (para movimientos normales 1v1).
- Evaluación heurística del tablero basada en la matriz de pesos posicionales (`POSITION_WEIGHTS`).
- Heurística greedy para movimientos normales en 4P (flips + peso posicional).

## Sistema de Decisión de Habilidades (3 Capas)

### Capa 1 — Condiciones mínimas
Cada habilidad tiene un filtro previo: si no se cumplen condiciones mínimas (e.g., bomb necesita ≥2 fichas rivales en el radio), la skill se descarta.

### Capa 2 — Prioridad de uso (Heurística)
La IA solo usa una skill si su `skill_score >= best_normal_score`.
- `best_normal_score` se calcula simulando todos los movimientos válidos normales con una evaluación rápida (ganancia de fichas + peso posicional).
- Cada skill tiene su propia fórmula de `skill_score` basada en el impacto estimado.

### Capa 3 — Gestión de inventario en endgame
Cuando quedan <15% de casillas vacías:
- Se añade un bonus de +2 a cada `skill_score` para reflejar la penalización evitada.
- Skills normalmente inútiles (`lose_turn`, `give_skill`) se consideran usables para evitar la penalización de -2 pts por skill sin usar al final de la partida.