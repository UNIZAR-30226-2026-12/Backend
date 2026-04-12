from persistence.database import database


async def run_migrations():
    """
    Migraciones DDL que se ejecutan una única vez al arrancar el servidor.
    Añadir aquí cualquier nueva migración de esquema.
    """

    # --- friend_messages ---
    await database.execute("""
        CREATE TABLE IF NOT EXISTS friend_messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            is_read BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await database.execute("""
        CREATE INDEX IF NOT EXISTS idx_friend_messages_pair_created_at
        ON friend_messages (sender_id, receiver_id, created_at)
    """)
    await database.execute("""
        CREATE INDEX IF NOT EXISTS idx_friend_messages_receiver_unread
        ON friend_messages (receiver_id, is_read)
    """)

    # --- lobby_invites ---
    await database.execute("""
        CREATE TABLE IF NOT EXISTS lobby_invites (
            id SERIAL PRIMARY KEY,
            lobby_id INTEGER NOT NULL REFERENCES lobbies(id) ON DELETE CASCADE,
            invited_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invited_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invite_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lobby_id, invited_id)
        )
    """)

    await database.execute("""
        UPDATE lobby_invites
        SET invited_user_id = invited_id
        WHERE invited_user_id IS NULL AND invited_id IS NOT NULL
    """)
    await database.execute("""
        UPDATE lobby_invites
        SET invited_id = invited_user_id
        WHERE invited_id IS NULL AND invited_user_id IS NOT NULL
    """)
