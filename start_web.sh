#!/usr/bin/env bash

CWD=`pwd`

export PYTHONPATH="PYTHONPATH:$CWD/web/backend/"

cd "$CWD/web/backend/app"

uvicorn main:app --host 0.0.0.0 --port 8000

