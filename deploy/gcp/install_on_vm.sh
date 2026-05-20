#!/bin/bash
# FitBook scraper - GCP VM one-time setup (Ubuntu 22.04/24.04)
# Run on the VM after uploading project files to /opt/fitbook-scraper
set -euo pipefail

APP_DIR="/opt/fitbook-scraper"
LOG_DIR="/var/log/fitbook-scraper"
VENV="${APP_DIR}/.venv"
WRAPPER="${APP_DIR}/run_scrape.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root: sudo bash install_on_vm.sh"
  exit 1
fi

if [[ ! -f "${APP_DIR}/scrape_fitbook.py" ]]; then
  echo "Missing ${APP_DIR}/scrape_fitbook.py"
  echo "Upload project files to ${APP_DIR} first, then run this script again."
  exit 1
fi

apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip

mkdir -p "${LOG_DIR}"
chmod 755 "${LOG_DIR}"

if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --upgrade pip -q
"${VENV}/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

if [[ ! -f "${APP_DIR}/config.json" ]]; then
  echo "WARNING: config.json not found. Copy config.json before first scrape."
fi

if [[ ! -f "${APP_DIR}/google_service_account.json" ]]; then
  echo "WARNING: google_service_account.json not found. Upload it before first scrape."
fi

if [[ -f "${APP_DIR}/deploy/gcp/fitbook.env.example" && ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/deploy/gcp/fitbook.env.example" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env - edit FITBOOK_COOKIE there."
fi

cat > "${WRAPPER}" <<'WRAP'
#!/bin/bash
set -euo pipefail
APP_DIR="/opt/fitbook-scraper"
cd "$APP_DIR"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec .venv/bin/python scrape_fitbook.py
WRAP
chmod +x "${WRAPPER}"

CRON_FILE="/etc/cron.d/fitbook-scraper"
cat > "${CRON_FILE}" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Every hour at minute 50 (VM timezone, usually Asia/Taipei)
50 * * * * root ${WRAPPER} >> ${LOG_DIR}/scrape.log 2>&1
EOF
chmod 644 "${CRON_FILE}"

timedatectl set-timezone Asia/Taipei 2>/dev/null || true

echo ""
echo "=== Install done ==="
echo "App:    ${APP_DIR}"
echo "Run:    sudo ${WRAPPER}"
echo "Logs:   ${LOG_DIR}/scrape.log"
echo "Cron:   every hour at :50"
echo ""
echo "Test now: sudo ${WRAPPER}"
