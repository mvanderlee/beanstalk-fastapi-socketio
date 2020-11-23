#!/usr/bin/env sh

exec gunicorn --config="python:app.gunicorn" app.app:app
