-- Creación de funciones útiles
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Tabla de Usuarios
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    elo INTEGER NOT NULL DEFAULT 1000,
    avatar_url TEXT,
    preferred_piece_color VARCHAR(20) DEFAULT 'black',
    preferred_board_color VARCHAR(20) DEFAULT 'green',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_users_modtime
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

-- Tabla de Amigos
CREATE TABLE friendships (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, accepted, rejected
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, friend_id)
);

CREATE TRIGGER update_friendships_modtime
BEFORE UPDATE ON friendships
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

-- Tabla de Salas (Lobbies)
CREATE TABLE lobbies (
    id SERIAL PRIMARY KEY,
    creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_public BOOLEAN NOT NULL DEFAULT true,
    mode VARCHAR(50) NOT NULL DEFAULT '1vs1', -- 1vs1, 1vs1vs1vs1
    status VARCHAR(20) NOT NULL DEFAULT 'waiting', -- waiting, in_game, finished
    join_code VARCHAR(10) UNIQUE, -- Código corto para salas privadas
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Partidas
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    lobby_id INTEGER REFERENCES lobbies(id) ON DELETE SET NULL,
    player1_id INTEGER REFERENCES users(id),
    player2_id INTEGER REFERENCES users(id),
    player3_id INTEGER REFERENCES users(id),
    player4_id INTEGER REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'ongoing', -- ongoing, finished, aborted
    winner_id INTEGER REFERENCES users(id),
    mode VARCHAR(50) NOT NULL DEFAULT '1vs1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_games_modtime
BEFORE UPDATE ON games
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

-- Tabla de Movimientos
CREATE TABLE moves (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES users(id),
    move_number INTEGER NOT NULL,
    row_idx INTEGER NOT NULL,
    col_idx INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
