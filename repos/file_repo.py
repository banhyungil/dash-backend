"""Repository for ingested_files table CRUD and queries."""
from services import database


def record_ingested_file(source_path: str, filename: str, file_type: str,
                         cycles_count: int, skipped_count: int, error_count: int):
    """Record a file as ingested."""
    conn = database.get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO ingested_files
                (source_path, filename, file_type, cycles_count, skipped_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_path, filename, file_type, cycles_count, skipped_count, error_count))
        conn.commit()
    finally:
        conn.close()


def is_file_ingested(source_path: str) -> bool:
    """Check if a file has already been ingested."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM ingested_files WHERE source_path = ?", (source_path,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()
