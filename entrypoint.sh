#!/usr/bin/env sh

if [ "$INIT_DB" = "true" ]; then
  echo "Initializing DB"
  alembic upgrade head
  echo "DB Initialized\n"
else
  echo "Skipping DB initialization '$INIT_DB'"
fi

exec gunicorn --config="python:app.gunicorn" app.app:app
