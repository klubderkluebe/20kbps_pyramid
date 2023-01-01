#!/bin/bash
if [ -f pyramidprj.sqlite ]; then
    rm pyramidprj.sqlite
fi

alembic -c development.ini upgrade head && \
initialize_pyramidprj_db development.ini
