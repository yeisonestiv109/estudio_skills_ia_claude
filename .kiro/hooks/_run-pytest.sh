#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /home/estiv12/proyecto_cliente_catalina/estudio_skills_ia_claude || exit 1
uv run pytest tests/ -q --tb=short
