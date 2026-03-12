# Módulo: WS (Realtime Gateway)

**Responsabilidad:**
Manejo de las conexiones persistentes vía WebSockets para el tiempo real.

**Eventos y Tópicos:**
- `room_sync`: Sincronización de jugadores en la sala de espera.
- `game_state_update`: Emisión del estado del tablero, habilidades y turnos.
- `player_move`: Recepción de movimientos de clientes.
- `use_ability`: Recepción del uso de habilidades especiales.