"""Repository for h_ingested_file table CRUD and queries."""
from services import database


def upsert(source_path: str, filename: str, file_type: str,
           cycles_count: int, skipped_count: int, error_count: int,
           conn=None):
    """Record or update a file as ingested. If conn provided, does NOT commit."""
    own_conn = conn is None
    if own_conn:
        conn = database.get_connection()
    try:
        conn.execute("""
            INSERT INTO h_ingested_file
                (source_path, filename, file_type, cycles_count, skipped_count, error_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_path) DO UPDATE SET
                filename = EXCLUDED.filename,
                file_type = EXCLUDED.file_type,
                cycles_count = EXCLUDED.cycles_count,
                skipped_count = EXCLUDED.skipped_count,
                error_count = EXCLUDED.error_count,
                ingested_at = NOW()
        """, (source_path, filename, file_type, cycles_count, skipped_count, error_count))
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def exists_by_path(source_path: str) -> bool:
    """Check if a file has already been ingested."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM h_ingested_file WHERE source_path = %s", (source_path,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()
