#!/bin/bash
set -e

# ── DBus (required for QGIS master-password keyring) ─────────────────────────
rm -f /run/dbus/pid
mkdir -p /run/dbus
dbus-daemon --system --fork || true
eval "$(dbus-launch --sh-syntax)" || true
export DBUS_SESSION_BUS_ADDRESS

# ── xdg-open wrapper (opens OAuth2 URLs in Chrome inside the container) ───────
cat > /usr/local/bin/xdg-open << 'XDGEOF'
#!/bin/bash
google-chrome --no-sandbox --no-first-run --no-default-browser-check \
    --disable-gpu --disable-dev-shm-usage "$@"
XDGEOF
chmod +x /usr/local/bin/xdg-open

# ── Plugin symlink ────────────────────────────────────────────────────────────
# /plugin_src is the bind-mounted repo root. We symlink the plugin package into
# the QGIS user plugins directory so QGIS loads it, and any code change on the
# host is picked up immediately after a plugin reload (no rebuild needed).
PLUGIN_DIR="/root/.local/share/QGIS/QGIS4/profiles/default/python/plugins"
PLUGIN_NAME="rana_qgis_plugin"
PLUGIN_SRC="/plugin_src/${PLUGIN_NAME}"

mkdir -p "$PLUGIN_DIR"
ln -sfn "$PLUGIN_SRC" "$PLUGIN_DIR/$PLUGIN_NAME"

echo ""
echo "  QGIS 4.2 dev environment"
echo "  Plugin : $PLUGIN_DIR/$PLUGIN_NAME -> $PLUGIN_SRC"
echo "  Files  : ~/local_files  (host: ./local_files)"
echo "  Close the QGIS window normally to save settings (theme etc.)"
echo ""

exec qgis
