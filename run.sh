#!/usr/bin/env bash
python3 -m wyoming_google \
    --uri "tcp://0.0.0.0:10555" \
    --config /config "${@:2}"