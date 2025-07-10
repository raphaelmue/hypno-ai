# Database Migrations with Alembic

This directory contains database migration scripts managed by Alembic. These scripts are used to create and update the database schema.

## Migration Files

- `env.py`: Configuration for Alembic, including database connection settings
- `script.py.mako`: Template for generating migration scripts
- `versions/`: Directory containing individual migration scripts

## How Migrations Work

When the application starts, it automatically checks for and applies any pending migrations. This ensures that the database schema is always up to date.

## Creating a New Migration

To create a new migration script, you can use the `create_migration` function from the `app.models.migrations` module:

```python
from app.models.migrations import create_migration

# Create a new migration with a descriptive message
create_migration("Add new column to routines table")
```

This will generate a new migration script in the `versions/` directory.

## Migration Script Structure

Each migration script contains two main functions:

1. `upgrade()`: Code to apply the migration (e.g., add a column, create a table)
2. `downgrade()`: Code to revert the migration (e.g., drop a column, drop a table)

Example:

```python
def upgrade() -> None:
    # Add a new column to the routines table
    op.add_column('routines', sa.Column('description', sa.String(), nullable=True))

def downgrade() -> None:
    # Drop the column when downgrading
    op.drop_column('routines', 'description')
```

## Manual Migration Commands

If you need to run migrations manually, you can use the Alembic command-line interface:

```
# Upgrade to the latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Get current version
alembic current

# Create a new migration script
alembic revision -m "Description of changes"
```

## Troubleshooting

If you encounter issues with migrations:

1. Check the application logs for error messages
2. Verify that the database file exists and is accessible
3. Ensure that the migration scripts are properly sequenced (check the `down_revision` values)