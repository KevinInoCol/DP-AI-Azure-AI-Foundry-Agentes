#!/usr/bin/env bash
# Sincroniza las skills versionadas del repo (.claude/skills/) desde su fuente de
# autoría, las skills globales del autor (~/.claude/skills/). Ver docs/adr/0002.
#
# Uso (desde cualquier carpeta del repo):
#   bash .claude/scripts/sync-skills.sh --check   # informa diferencias; exit 1 si hay
#   bash .claude/scripts/sync-skills.sh           # copia global -> repo las que difieren
#
# Solo toca skills que YA existen en el repo (la lista de skills del taller la decide
# el repo, no la carpeta global). Para añadir una skill nueva al taller:
#   cp -R ~/.claude/skills/<skill> .claude/skills/ && bash .claude/scripts/sync-skills.sh
# Las skills que solo existen en el repo se dejan como están (se informan).

set -euo pipefail

RAIZ=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
REPO="$RAIZ/.claude/skills"
GLOBAL="${SKILLS_GLOBAL_DIR:-$HOME/.claude/skills}"
MODO="${1:-sync}"
DIFIEREN=0

[ -d "$GLOBAL" ] || { echo "No existe $GLOBAL: en esta máquina el repo es la única fuente; nada que sincronizar."; exit 0; }

for dir in "$REPO"/*/; do
  skill=$(basename "$dir")
  if [ -L "${dir%/}" ]; then
    echo "  ⚠️  $skill es un enlace simbólico: el repo debe contener copias reales (ADR 0002)."; DIFIEREN=$((DIFIEREN + 1)); continue
  fi
  if [ ! -d "$GLOBAL/$skill" ]; then
    echo "  ·  $skill: solo en el repo (sin fuente global)"; continue
  fi
  if diff -rq --exclude=__pycache__ --exclude=.DS_Store "$GLOBAL/$skill" "$dir" >/dev/null; then
    echo "  ✅ $skill"
    continue
  fi
  DIFIEREN=$((DIFIEREN + 1))
  if [ "$MODO" = "--check" ]; then
    echo "  ❌ $skill difiere:"
    diff -rq --exclude=__pycache__ --exclude=.DS_Store "$GLOBAL/$skill" "$dir" | sed "s#$GLOBAL/#global:#; s#$REPO/#repo:#; s/^/       /" || true
  else
    rsync -a --delete --exclude=__pycache__ --exclude=.DS_Store "$GLOBAL/$skill/" "$dir"
    echo "  🔄 $skill sincronizada desde $GLOBAL"
  fi
done

if [ "$MODO" = "--check" ] && [ "$DIFIEREN" -gt 0 ]; then
  echo "$DIFIEREN skill(s) desalineadas. Ejecuta: bash .claude/scripts/sync-skills.sh"
  exit 1
fi
