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

    # NOTE: La tabla lobby_invites ya existe en Supabase, no es necesario crearla aquí
