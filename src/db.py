from pathlib import Path

from src.config import mysql_database_name, mysql_url


def get_engine(include_database: bool = True):
    from sqlalchemy import create_engine

    return create_engine(mysql_url(include_database), pool_pre_ping=True)


def create_database_if_needed() -> None:
    from sqlalchemy import text

    database = mysql_database_name()
    engine = get_engine(include_database=False)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    engine.dispose()


def test_connection() -> str:
    from sqlalchemy import text

    with get_engine().connect() as connection:
        return connection.execute(text("SELECT VERSION()" )).scalar_one()


def split_sql_statements(sql: str) -> list[str]:
    statements = []
    buffer = []
    quote = None
    escaped = False
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        for char in line + "\n":
            if escaped:
                buffer.append(char)
                escaped = False
                continue
            if char == "\\" and quote:
                buffer.append(char)
                escaped = True
                continue
            if char in {"'", '"', "`"}:
                if quote is None:
                    quote = char
                elif quote == char:
                    quote = None
                buffer.append(char)
                continue
            if char == ";" and quote is None:
                statement = "".join(buffer).strip()
                if statement:
                    statements.append(statement)
                buffer = []
            else:
                buffer.append(char)
    final = "".join(buffer).strip()
    if final:
        statements.append(final)
    return statements


def execute_sql_file(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with get_engine().begin() as connection:
        for statement in split_sql_statements(sql):
            connection.exec_driver_sql(statement)
