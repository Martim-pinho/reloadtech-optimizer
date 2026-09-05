#!/usr/bin/env bash
# Constrói um .deb instalável com `sudo apt install ./reloadtech-optimizer_1.0.0_all.deb`.
# Corre em qualquer máquina com dpkg-deb (Debian, Ubuntu, ou macOS com `brew install dpkg`).
set -euo pipefail

VERSAO="1.0.0"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRABALHO="${RAIZ}/build/deb"
PACOTE="${TRABALHO}/reloadtech-optimizer_${VERSAO}_all"

rm -rf "$TRABALHO"
mkdir -p "$PACOTE/DEBIAN" \
         "$PACOTE/opt/reloadtech-optimizer" \
         "$PACOTE/usr/bin" \
         "$PACOTE/lib/systemd/system" \
         "$PACOTE/usr/share/applications" \
         "$PACOTE/usr/share/doc/reloadtech-optimizer"

cp -r "${RAIZ}/reloadtech" "$PACOTE/opt/reloadtech-optimizer/"
cp "${RAIZ}/pyproject.toml" "${RAIZ}/README.md" "$PACOTE/opt/reloadtech-optimizer/"
cp "${RAIZ}/LICENSE" "$PACOTE/usr/share/doc/reloadtech-optimizer/copyright"
cp "${RAIZ}/packaging/reloadtech-manutencao.service" \
   "${RAIZ}/packaging/reloadtech-manutencao.timer" "$PACOTE/lib/systemd/system/"

cat > "$PACOTE/DEBIAN/control" <<CONTROL
Package: reloadtech-optimizer
Version: ${VERSAO}
Section: admin
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-psutil
Recommends: python3-reportlab, smartmontools
Suggests: python3-pyside6.qtwidgets
Maintainer: Martim Pinho <martimpinho06@hotmail.com>
Description: Diagnostico e otimizacao de sistemas
 Ferramenta de diagnostico, limpeza, gestao de arranque e otimizacao para
 Windows, macOS e Linux. Em servidores funciona inteiramente por linha de
 comandos e gera relatorios HTML de manutencao.
 .
 A interface grafica e opcional e so e necessaria em maquinas com ambiente
 de trabalho.
CONTROL

# O comando entra no PATH a apontar para o codigo em /opt
cat > "$PACOTE/usr/bin/reloadtech" <<'LANCADOR'
#!/bin/sh
exec python3 -c "import sys; sys.path.insert(0, '/opt/reloadtech-optimizer'); from reloadtech.cli import main; sys.exit(main())" "$@"
LANCADOR
chmod 755 "$PACOTE/usr/bin/reloadtech"

cat > "$PACOTE/usr/share/applications/reloadtech-optimizer.desktop" <<'ATALHO'
[Desktop Entry]
Type=Application
Name=ReloadTech Optimizer
Comment=Diagnóstico e otimização do sistema
Exec=reloadtech --gui
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Settings;
ATALHO

cat > "$PACOTE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
mkdir -p /var/log/reloadtech
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
    echo "Manutenção semanal automática (opcional):"
    echo "  sudo systemctl enable --now reloadtech-manutencao.timer"
fi
POSTINST
chmod 755 "$PACOTE/DEBIAN/postinst"

cat > "$PACOTE/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if [ -d /run/systemd/system ]; then
    systemctl disable --now reloadtech-manutencao.timer 2>/dev/null || true
fi
PRERM
chmod 755 "$PACOTE/DEBIAN/prerm"

dpkg-deb --build --root-owner-group "$PACOTE"
mv "${PACOTE}.deb" "${RAIZ}/build/"
echo
echo "Pacote pronto: build/reloadtech-optimizer_${VERSAO}_all.deb"
echo "Instalar:  sudo apt install ./build/reloadtech-optimizer_${VERSAO}_all.deb"
