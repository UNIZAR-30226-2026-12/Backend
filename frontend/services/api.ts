import { Player, BoardState, Coordinates } from '../types';

/**
 * En entornos de desarrollo locales, el backend suele estar en el puerto 8000.
 * En entornos de sandbox/cloud, el backend suele servirse en el mismo host.
 */
const getBaseUrl = () => {
  // En producción (Docker/Nginx) y Desarrollo (Vite con Proxy),
  // las llamadas deben ser relativas a la raíz (ej: /partida).
  // Solo devolvemos cadena vacía para que fetch use la URL actual del navegador.
  // Si necesitamos URL absoluta por alguna razón (ej. SSR), se podría configurar.

  // Excepción: Si estamos corriendo tests o algo fuera de contexto navegador.
  if (typeof window !== 'undefined') {
    return '';
  }
  return 'http://localhost:8081'; // Fallback para tests/server-side
};

const API_URL = getBaseUrl();

export interface BackendGameState {
  game_id: string;
  board: BoardState;
  current_player: Player;
  winner: Player | 'draw' | null;
  game_over: boolean;
  score: { black: number; white: number };
  valid_moves: Coordinates[];
  last_move?: Coordinates | null;
}

export const createGame = async (): Promise<BackendGameState> => {
  const response = await fetch(`${API_URL}/partida`, {
    method: 'POST',
    mode: 'cors'
  });
  if (!response.ok) throw new Error('Servidor no responde');
  return await response.json();
};

export const makeMove = async (gameId: string, row: number, col: number, player: Player): Promise<BackendGameState> => {
  const response = await fetch(`${API_URL}/movimiento`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, row, col, player }),
    mode: 'cors'
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Error en el servidor');
  }
  return await response.json();
};
