# Módulo: Persistence (Base de Datos)

**Responsabilidad:**
Aislar la capa de acceso a datos. Todo lo que requiera conectarse a PostgreSQL mediante la librería `databases` va aquí.

**Funcionalidades:**
- Archivo de conexión principal (ej. `db.py` o `database.py`).
- (Futuro) Modelos u operaciones de base de datos extraídas de los controladores, para no tener consultas SQL (`SELECT * FROM users...`) mezcladas con la lógica de red.