import sqlite3
from datetime import datetime

import click
from flask import current_app, g
import os


def get_db():
  if "db" not in g:
    g.db = sqlite3.connect(
      current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
    )
    g.db.row_factory = sqlite3.Row
    g.db.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints

  return g.db


def close_db(e=None):
  db = g.pop("db", None)

  if db is not None:
    db.close()


def init_db():
  """Initialize the database with schema"""
  db = get_db()

  # Get the schema file path
  schema_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "buyme_database.sql"
  )
  print(schema_path)

  with open(schema_path, "r") as f:
    db.executescript(f.read())

  db.commit()
  click.echo("Database initialized successfully.")


@click.command("init-db")
def init_db_command():
  """Clear the existing data and create new tables."""
  init_db()


def init_app(app):
  """Register database functions with the Flask app"""
  app.teardown_appcontext(close_db)
  app.cli.add_command(init_db_command)


sqlite3.register_converter("timestamp", lambda v: datetime.fromisoformat(v.decode()))
sqlite3.register_converter("datetime", lambda v: datetime.fromisoformat(v.decode()))
