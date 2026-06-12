from pathlib import Path


def test_migration_040_working_days_contains_required_schema_changes():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "040_add_working_days.py"
    )
    text = migration_path.read_text(encoding="utf-8")

    assert 'op.add_column(\n        "companies"' in text
    assert 'op.add_column(\n        "users"' in text
    assert "server_default=sa.text(\"'[0,1,2,3,4]'::jsonb\")" in text
    assert "UPDATE companies" in text
    assert "SET working_days = '[0,1,2,3,4]'::jsonb" in text
    assert 'op.drop_column("users", "working_days")' in text
    assert 'op.drop_column("companies", "working_days")' in text
