#!/bin/bash
echo "DROP DATABASE IF EXISTS pyramidprj; CREATE DATABASE pyramidprj;" | psql postgresql://postgres:postgres@localhost/
alembic -c development.ini upgrade head && \
initialize_pyramidprj_db development.ini
