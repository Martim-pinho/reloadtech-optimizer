#!/usr/bin/env bash
# Instalador universal para Linux e macOS.
#   curl -fsSL .../install.sh | bash              → instala só a linha de comandos
#   curl -fsSL .../install.sh | bash -s -- --gui  → instala também a interface gráfica
set -euo pipefail

COM_GUI=0
[[ "${1:-}" == "--gui" ]] && COM_GUI=1

echo "ReloadTech Optimizer — instalação"

command -v python3 >/dev/null || { echo "Erro: python3 não encontrado." >&2; exit 1; }

VERSAO=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
python3 - <<'PY' || { echo "Erro: é preciso Python 3.10 ou superior (tens $VERSAO)." >&2; exit 1; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRA="pdf"
[[ $COM_GUI -eq 1 ]] && EXTRA="completo"

# pipx isola as dependências e mantém o comando no PATH — é o caminho limpo
# em distribuições que protegem o Python do sistema (PEP 668).
if command -v pipx >/dev/null; then
    pipx install --force "${ORIGEM}[${EXTRA}]"
else
    echo "pipx não encontrado; a instalar num ambiente próprio em /opt."
    DESTINO=/opt/reloadtech-optimizer
    sudo python3 -m venv "$DESTINO"
    sudo "$DESTINO/bin/pip" install --quiet --upgrade pip
    sudo "$DESTINO/bin/pip" install --quiet "${ORIGEM}[${EXTRA}]"
    sudo ln -sf "$DESTINO/bin/reloadtech" /usr/local/bin/reloadtech
fi

echo
echo "Instalado. Experimenta:"
echo "  reloadtech diagnostico"
echo "  reloadtech limpeza"
[[ $COM_GUI -eq 1 ]] && echo "  reloadtech --gui"
echo
echo "Manutenção semanal automática (opcional):"
echo "  sudo cp packaging/reloadtech-manutencao.* /etc/systemd/system/"
echo "  sudo mkdir -p /var/log/reloadtech"
echo "  sudo systemctl enable --now reloadtech-manutencao.timer"
