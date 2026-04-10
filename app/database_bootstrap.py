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


def ensure_prediction_record_columns(database_uri):
    if not database_uri:
        return

    engine = create_engine(database_uri)
    statements = {
        "so2_pred": "ALTER TABLE prediction_records ADD COLUMN so2_pred FLOAT",
        "no2_pred": "ALTER TABLE prediction_records ADD COLUMN no2_pred FLOAT",
        "co_pred": "ALTER TABLE prediction_records ADD COLUMN co_pred FLOAT",
        "o3_pred": "ALTER TABLE prediction_records ADD COLUMN o3_pred FLOAT",
    }

    try:
        with engine.begin() as connection:
            table_names = set(connection.dialect.get_table_names(connection))
            if "prediction_records" not in table_names:
                return
            column_names = {
                column["name"]
                for column in connection.dialect.get_columns(connection, "prediction_records")
            }
            for column_name, statement in statements.items():
                if column_name in column_names:
                    continue
                connection.execute(text(statement))
    finally:
        engine.dispose()
