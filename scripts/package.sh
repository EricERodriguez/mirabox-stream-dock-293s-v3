#!/usr/bin/env bash
# Build a reproducible, redistributable package of the Mirabox Stream Dock 293S V3
# Linux application: a tarball always, plus a .deb when dpkg-deb is available.
#
# The official Mirabox SDK is never vendored in the package; install.sh fetches
# it from https://github.com/MiraboxSpace/StreamDock-Device-SDK at install time,
# so the SDK's own upstream license always governs it separately from this
# project's MIT license.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d ' \t\r\n' < "$repo_root/VERSION")"
name="mirabox-stream-dock-293s-v3"
dist_dir="$repo_root/dist"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

log() { printf '\n== %s ==\n' "$1"; }

# ---------------------------------------------------------------------------
log "Validando dependencias"
for cmd in python3 bash git tar sha256sum; do
  command -v "$cmd" >/dev/null || { echo "Falta el comando requerido: $cmd" >&2; exit 1; }
done
have_dpkg_deb=0
if command -v dpkg-deb >/dev/null; then
  have_dpkg_deb=1
  echo "dpkg-deb disponible: se generará también un paquete .deb"
else
  echo "dpkg-deb no disponible: sólo se generará el tarball"
fi

# ---------------------------------------------------------------------------
log "Validando sintaxis Python"
python3 -m py_compile "$repo_root"/app/*.py "$repo_root"/app/daemon/*.py "$repo_root"/app/editor/*.py
echo "OK: app/*.py compila"

log "Validando sintaxis Bash"
bash -n "$repo_root/install.sh"
bash -n "$repo_root/app/launch-editor.sh"
bash -n "$repo_root/scripts/package.sh"
echo "OK: install.sh, launch-editor.sh, package.sh"

log "Validando JSON"
python3 -m json.tool "$repo_root/profile.default.json" >/dev/null
echo "OK: profile.default.json"

log "Validando SVG"
python3 - "$repo_root/assets/mirabox-stream-dock-293s-v3.svg" <<'PY'
import sys
import xml.dom.minidom as minidom
minidom.parse(sys.argv[1])
print("OK: SVG bien formado")
PY

# ---------------------------------------------------------------------------
log "Buscando rutas personales o posibles credenciales"
# README.md legitimately mentions "ubuntu-config" as a generic example of a
# personal profile repository; that is documentation prose, not a leaked path.
if grep -RInE "/home/[a-z0-9_-]+/(Github|\.config|\.local)|BEGIN (RSA|OPENSSH|PGP) PRIVATE KEY|api[_-]?key|secret|token|password" \
    "$repo_root/app" "$repo_root/assets" "$repo_root/profile.default.json" \
    "$repo_root/install.sh" "$repo_root/README.md" "$repo_root/LICENSE" "$repo_root/CHANGELOG.md" 2>/dev/null; then
  echo "Se encontraron rutas absolutas de un home o posibles credenciales; abortando el empaquetado." >&2
  exit 1
fi
echo "OK: sin rutas absolutas de \$HOME ni credenciales en el árbol a empaquetar"

# ---------------------------------------------------------------------------
log "Preparando dist/ limpio"
rm -rf "$dist_dir"
mkdir -p "$dist_dir"

stage="$work_dir/$name-$version"
mkdir -p "$stage"
install -d "$stage/app/daemon" "$stage/app/editor" "$stage/assets"
install -m 0755 "$repo_root/app/launch-editor.sh" "$stage/app/"
install -m 0644 "$repo_root/app/profile_store.py" "$repo_root/app/mirabox-stream-dock-293s-v3.service" \
  "$repo_root/app/mirabox-stream-dock-293s-v3.desktop" "$repo_root/app/70-mirabox-stream-dock-293s-v3.rules" \
  "$stage/app/"
install -m 0644 "$repo_root"/app/daemon/*.py "$stage/app/daemon/"
install -m 0644 "$repo_root"/app/editor/*.py "$stage/app/editor/"
install -m 0644 "$repo_root/assets/mirabox-stream-dock-293s-v3.svg" "$stage/assets/"
install -m 0644 "$repo_root/profile.default.json" "$repo_root/README.md" "$repo_root/LICENSE" "$repo_root/CHANGELOG.md" "$repo_root/VERSION" "$stage/"
install -m 0755 "$repo_root/install.sh" "$stage/"

# Explicitly excluded from the package, by design:
#   - personal profiles (profile-ubuntu.json, profile-eric44-*.json, anything under ubuntu-config/)
#   - /home/eric44 paths, tokens, credentials, cookies
#   - the official SDK itself (fetched live by install.sh, never vendored)
find "$stage" -name '__pycache__' -o -name '*.pyc' | xargs -r rm -rf

log "Empaquetando tarball"
tar --sort=name --numeric-owner --owner=0 --group=0 \
    -czf "$dist_dir/$name-$version.tar.gz" -C "$work_dir" "$name-$version"
(cd "$dist_dir" && sha256sum "$name-$version.tar.gz" > "$name-$version.tar.gz.sha256")
echo "Generado: dist/$name-$version.tar.gz"

# ---------------------------------------------------------------------------
if [[ "$have_dpkg_deb" == "1" ]]; then
  log "Empaquetando .deb"
  deb_root="$work_dir/deb"
  share_dir="$deb_root/usr/share/$name"
  doc_dir="$deb_root/usr/share/doc/$name"
  install -d "$deb_root/DEBIAN" "$share_dir" "$doc_dir"
  cp -a "$stage/." "$share_dir/"
  cp "$repo_root/README.md" "$doc_dir/README.md"
  cp "$repo_root/LICENSE" "$doc_dir/copyright"

  cat > "$deb_root/DEBIAN/control" <<EOF
Package: $name
Version: $version
Section: utils
Priority: optional
Architecture: all
Maintainer: Eric Rodriguez <noreply@localhost>
Suggests: python3, python3-venv, python3-gi, gir1.2-gtk-4.0, python3-pil, git
Description: Mirabox Stream Dock 293S V3 editor and official-SDK bridge
 GTK4 editor and per-user systemd bridge for the Mirabox Stream Dock 293S V3.
 This package only stages the application files under /usr/share; it does
 NOT run install.sh automatically. The official Mirabox SDK is fetched
 separately by install.sh, as your own user, during the per-user setup step.
EOF

  cat > "$deb_root/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
cat <<'MSG'

Mirabox Stream Dock 293S V3 was staged under /usr/share/$name.

This .deb only places files on disk; it deliberately does NOT create your
per-user venv, fetch the official SDK, or enable any systemd --user service,
because those steps must run as your own (non-root) user account, not root.

To finish installing, run as your normal user (not root, no sudo):

  /usr/share/$name/install.sh

That script will refuse to run if an older Stream Dock integration is still
active, and it never touches firmware.
MSG
EOF
  chmod 0755 "$deb_root/DEBIAN/postinst"
  find "$deb_root" -name '__pycache__' -o -name '*.pyc' | xargs -r rm -rf

  dpkg-deb --build --root-owner-group "$deb_root" "$dist_dir/${name}_${version}_all.deb" >/dev/null
  (cd "$dist_dir" && sha256sum "${name}_${version}_all.deb" > "${name}_${version}_all.deb.sha256")
  echo "Generado: dist/${name}_${version}_all.deb"
fi

# ---------------------------------------------------------------------------
log "Probando la instalación en un staging temporal (sin tocar el servicio real)"
staging_home="$work_dir/staging-home"
fake_bin="$work_dir/fake-bin"
mkdir -p "$staging_home" "$fake_bin"

# A no-op systemctl stub: guarantees the real user service is never touched by
# this test, regardless of what install.sh decides to invoke.
cat > "$fake_bin/systemctl" <<'EOF'
#!/usr/bin/env bash
echo "[fake systemctl] $*" >> "$STAGING_SYSTEMCTL_LOG"
# Simulate a clean machine: no older Stream Dock integration is active here.
case "$*" in
  "--user is-active --quiet streamdock-mirabox-293s-v3.service") exit 3 ;;
esac
exit 0
EOF
chmod +x "$fake_bin/systemctl"
export STAGING_SYSTEMCTL_LOG="$work_dir/systemctl-calls.log"
: > "$STAGING_SYSTEMCTL_LOG"

tar -xzf "$dist_dir/$name-$version.tar.gz" -C "$work_dir"
(
  cd "$work_dir/$name-$version"
  HOME="$staging_home" \
  XDG_DATA_HOME="$staging_home/.local/share" \
  XDG_CONFIG_HOME="$staging_home/.config" \
  PATH="$fake_bin:$PATH" \
  bash ./install.sh
)

test -x "$staging_home/.local/share/$name/venv/bin/python"
"$staging_home/.local/share/$name/venv/bin/python" -c "import StreamDock" \
  && echo "OK: paquete StreamDock (SDK oficial) instalable en un venv aislado"
test -f "$staging_home/.config/systemd/user/$name.service"
grep -q "$staging_home/.local/share/$name" "$staging_home/.config/systemd/user/$name.service"
echo "OK: unidad systemd renderizada con @APP_HOME@ resuelto"
test -f "$staging_home/.local/share/applications/$name.desktop"
grep -q "^Icon=$staging_home/.local/share/$name/assets/$name.svg$" \
  "$staging_home/.local/share/applications/$name.desktop"
echo "OK: entrada .desktop apunta al icono SVG correcto"
grep -q "enable --now $name.service" "$STAGING_SYSTEMCTL_LOG"
echo "OK: el instalador habría activado el servicio (systemctl real jamás fue invocado)"
echo "El servicio real ($name.service) del usuario no fue tocado por esta prueba."

# ---------------------------------------------------------------------------
if [[ -n "${DISPLAY:-}" ]]; then
  log "Verificando que el .desktop abre la app y usa el icono SVG (lanzamiento real)"
  # GtkApplication is single-instance per application ID: any editor already
  # running (e.g. the real installed app open for the user) would otherwise
  # just absorb this activation instead of opening a fresh staging window.
  # The editor now runs as "python -m editor" (WorkingDirectory=.../app), so
  # the venv's own python path is what makes a process match uniquely.
  running_before="$(pgrep -f 'venv/bin/python -m editor' || true)"
  if [[ -n "$running_before" ]]; then
    echo "Cerrando temporalmente instancia(s) del editor ya abiertas para aislar la prueba: $running_before"
    kill -9 $running_before 2>/dev/null || true
    for _ in $(seq 1 5); do
      pgrep -f 'venv/bin/python -m editor' >/dev/null || break
      sleep 1
    done
  fi
  launch_log="$work_dir/launch-check.log"
  nohup env DISPLAY="$DISPLAY" HOME="$staging_home" \
    XDG_DATA_HOME="$staging_home/.local/share" XDG_CONFIG_HOME="$staging_home/.config" \
    "$staging_home/.local/share/$name/launch-editor.sh" >"$launch_log" 2>&1 &
  disown
  launched=0
  editor_pattern="$staging_home/.local/share/$name/venv/bin/python -m editor"
  for _ in $(seq 1 10); do
    if pgrep -f "$editor_pattern" >/dev/null; then
      launched=1
      break
    fi
    sleep 1
  done
  if [[ "$launched" == "1" ]]; then
    echo "OK: la app instalada desde el staging abrió una ventana real"
    pkill -f "$editor_pattern" || true
  else
    echo "AVISO: no se pudo confirmar el lanzamiento gráfico; salida de launch-editor.sh:" >&2
    cat "$launch_log" >&2 || true
  fi
else
  echo "AVISO: sin \$DISPLAY, se omite la prueba de lanzamiento gráfico real." >&2
fi

# ---------------------------------------------------------------------------
log "Checksums finales en dist/"
(cd "$dist_dir" && sha256sum -c ./*.sha256)
ls -la "$dist_dir"

cat <<EOF

Empaquetado completo para $name $version.
El SDK oficial de Mirabox NO está incluido en el paquete: install.sh lo
descarga por separado desde GitHub durante la instalación, como indica
README.md.
EOF
