#!/bin/sh

docker run --rm -p 8000:8000 --env-file .env boost-dev

# in the terminal type:  ./run-docker.sh