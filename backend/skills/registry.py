import random

# Lista oficial de las 12 habilidades
SKILLS_LIST = [
    "gravity",       # 1. Gravedad (eliges dirección)
    "bomb",          # 2. Bomba 3x3
    "fix_piece",     # 3. Poner ficha fija
    "unfix_piece",   # 4. Quitar ficha fija
    "place_free",    # 5. Ficha libre
    "skip_rival",    # 6. Saltar turno rival
    "lose_turn",     # 7. Pierdes tu turno
    "flip_rival",    # 8. Voltear ficha rival
    "swap_colors",   # 9. Intercambio de color
    "steal_skill",   # 10. Robar habilidad
    "exchange_skill",# 11. Intercambiar habilidad
    "give_skill"     # 12. Dar habilidad
]

def get_random_skill() -> str:
    """Retorna una habilidad aleatoria de la lista oficial."""
    return random.choice(SKILLS_LIST)

# --- Metadata de Habilidades (Para futuro uso de la IA y Dispatcher) ---
SKILLS_CONFIG = {
    "gravity": {"needs_target": False, "needs_direction": True},
    "bomb": {"needs_target": True, "needs_direction": False},
    "fix_piece": {"needs_target": True, "needs_direction": False},
    "unfix_piece": {"needs_target": True, "needs_direction": False},
    "place_free": {"needs_target": True, "needs_direction": False},
    "skip_rival": {"needs_target": False, "needs_direction": False},
    "lose_turn": {"needs_target": False, "needs_direction": False},
    "flip_rival": {"needs_target": True, "needs_direction": False},
    "swap_colors": {"needs_target": True, "needs_direction": False},
    "steal_skill": {"needs_target": True, "needs_direction": False},
    "exchange_skill": {"needs_target": True, "needs_direction": False},
    "give_skill": {"needs_target": True, "needs_direction": False},
}
