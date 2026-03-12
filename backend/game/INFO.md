# Módulo: Game (Orquestador de Partida)

**Responsabilidad:**
Es el núcleo central de la partida en ejecución (Game Session Orchestrator). Coordina el estado de la partida, administra a los jugadores y pasa el tablero al motor de reglas.

**Funcionalidades:**
- Inicialización del tablero según el modo (8x8 o 16x16).
- Gestión del ciclo de turnos (saber a quién le toca jugar).
- Detección de fin de partida cuando no hay movimientos válidos.