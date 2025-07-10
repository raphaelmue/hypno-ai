import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import MetaData, Table, Column, String, Text

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# Import the settings module to get the database file path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.models.settings import settings

# Override the SQLAlchemy URL with the actual database file path
db_file = settings.get_db_file()
db_url = f"sqlite:///{db_file}"
config.set_main_option("sqlalchemy.url", db_url)

# Define the table structure for the routines table
def define_tables(meta):
    Table('routines', meta,
          Column('id', String, primary_key=True),
          Column('name', String, nullable=False),
          Column('text', Text, nullable=False),
          Column('language', String, nullable=False),
          Column('voice_type', String, nullable=False),
          Column('voice_id', String),
          Column('output_filename', String),
          Column('created_at', String, nullable=False),
          Column('updated_at', String, nullable=False)
          )

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Create a metadata object with our table definitions
        meta = MetaData()
        define_tables(meta)
        
        context.configure(
            connection=connection,
            target_metadata=meta,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()