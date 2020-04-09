#!/bin/bash
[[ "$1" == '--build' ]] && sudo docker build --build-arg UID=$(id -u) -t lightfaith/ensa .
docker run --rm -it -v $PWD/files:/ensa/files --user $(id -u):$(id -g) --name ensa lightfaith/ensa
