#!/bin/bash

# Requires venv configured at .venv

caddy reload --config caddy
.venv/bin/python3 main.py