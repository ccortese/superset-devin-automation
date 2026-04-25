#!/bin/bash
# Simulate a GitHub issue labeled webhook for local testing.
#
# Usage:
#   ./scripts/simulate_webhook.sh
#   ./scripts/simulate_webhook.sh 3 "[SECURITY] Subprocess shell injection"
#   WEBHOOK_SECRET=mysecret ./scripts/simulate_webhook.sh 1 "custom title"
#
# Environment:
#   WEBHOOK_SECRET  — must match the value in your .env (default: changeme)
#   WEBHOOK_URL     — target URL (default: http://localhost:8000/webhook)

set -e

ISSUE_NUMBER="${1:-1}"
ISSUE_TITLE="${2:-"[SECURITY] Test vulnerability"}"
WEBHOOK_URL="${WEBHOOK_URL:-"http://localhost:8000/webhook"}"
SECRET="${WEBHOOK_SECRET:-"changeme"}"

PAYLOAD=$(cat <<EOF
{
  "action": "labeled",
  "label": {"name": "devin-remediate"},
  "issue": {
    "number": ${ISSUE_NUMBER},
    "title": "${ISSUE_TITLE}",
    "body": "Simulated vulnerability body for issue ${ISSUE_NUMBER}. Triggered via simulate_webhook.sh.",
    "html_url": "https://github.com/testuser/superset/issues/${ISSUE_NUMBER}"
  },
  "repository": {
    "full_name": "testuser/superset"
  }
}
EOF
)

SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print "sha256="$2}')

echo ""
echo "→ Sending webhook for issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}"
echo "→ Target: ${WEBHOOK_URL}"
echo ""

curl -s -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD" | python3 -m json.tool

echo ""
