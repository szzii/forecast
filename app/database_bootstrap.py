from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


MYSQL_DRIVERS = {"mysql", "mysql+pymysql"}


def ensure_database_exists(database_uri):
    if not database_uri:
        return

    url = make_url(database_uri)
    if url.drivername not in MYSQL_DRIVERS or not url.database:
        return

    server_url = url.set(database=None)
    engine = create_engine(server_url)
    database_name = url.database

    try:
        with engine.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote_identifier(database_name)
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS {quoted_name} CHARACTER SET utf8mb4"))
            connection.commit()
    finally:
        engine.dispose()
