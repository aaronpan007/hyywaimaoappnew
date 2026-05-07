"""Helpers for repairing Postgres sequences after seeded explicit IDs."""

from sqlalchemy import text


async def sync_company_profiles_id_sequence(db) -> None:
    """Set company_profiles.id sequence to max(id) so the next insert is safe."""
    await db.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('company_profiles', 'id'),
                COALESCE((SELECT MAX(id) FROM company_profiles), 0) + 1,
                false
            )
            """
        )
    )
