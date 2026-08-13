#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /home/estiv12/proyecto_cliente_catalina/estudio_skills_ia_claude || exit 1
uv run ruff format src/ tests/ && uv run ruff check --fix src/ tests/
