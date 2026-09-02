#!/usr/bin/env bash
# ============================================================================
# LA COMPUERTA del loop de desarrollo del bot ARTF.
# Verde = objetivo alcanzado. Rojo = sigo iterando.
# Ver LOOPS.md para el contexto.
# ============================================================================
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$AQUI/../../../artf-pipeline-app"
FALLOS=0

titulo() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()     { printf '\033[32m  PASA\033[0m  %s\n' "$1"; }
malo()   { printf '\033[31m  FALLA\033[0m %s\n' "$1"; FALLOS=$((FALLOS+1)); }

titulo "1+3. Tests del bot (router, seguridad, cumplimiento del playbook)"
if (cd "$AQUI/Scrips_Worker_and_AppScript" && node --test "tests/*.test.js" >/tmp/artf_tests.log 2>&1); then
  ok "$(grep -E '^ℹ pass' /tmp/artf_tests.log | tr -d '\n')"
else
  malo "tests del bot"
  grep -E '^✖|AssertionError|\[R[0-9]' /tmp/artf_tests.log | head -20
fi

titulo "2. Type-check del dashboard"
if [ -d "$APP" ]; then
  if (cd "$APP" && npm run type-check >/tmp/artf_tsc.log 2>&1); then
    ok "tsc sin errores"
  else
    malo "type-check"
    tail -15 /tmp/artf_tsc.log
  fi
else
  malo "no encuentro artf-pipeline-app en $APP"
fi

titulo "4. Smoke de las RPC contra la base real"
echo "  (manual por ahora: ver LOOPS.md seccion 1, compuerta 4)"

titulo "5. Smoke HTTP del Worker"
if [ -n "${BOT_WORKER_URL:-}" ] && [ -n "${BOT_WEBHOOK_SECRET:-}" ]; then
  COD_SIN=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BOT_WORKER_URL" \
    -H 'Content-Type: application/json' -d '{"manychat_subscriber_id":"1","last_text":"hola"}')
  [ "$COD_SIN" = "401" ] && ok "sin secreto -> 401" || malo "sin secreto devolvio $COD_SIN (se esperaba 401)"
  COD_CON=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BOT_WORKER_URL" \
    -H 'Content-Type: application/json' -H "X-Bot-Secret: $BOT_WEBHOOK_SECRET" \
    -d '{"manychat_subscriber_id":"999888777","last_text":"CONTROL","first_name":"Smoke"}')
  [ "$COD_CON" = "200" ] && ok "con secreto -> 200" || malo "con secreto devolvio $COD_CON"
else
  echo "  (omitido: exporta BOT_WORKER_URL y BOT_WEBHOOK_SECRET cuando este desplegado)"
fi

printf '\n'
if [ "$FALLOS" -eq 0 ]; then
  printf '\033[32m\033[1mCOMPUERTA EN VERDE\033[0m\n'; exit 0
else
  printf '\033[31m\033[1mCOMPUERTA EN ROJO — %s fallo(s)\033[0m\n' "$FALLOS"; exit 1
fi
