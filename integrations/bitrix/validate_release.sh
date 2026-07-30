#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

required_files=(
  "elixir.promo/include.php"
  "elixir.promo/install/index.php"
  "elixir.promo/install/tools/api.php"
  "elixir.promo/lib/Service/PromoService.php"
  "elixir.reviewsync/include.php"
  "elixir.reviewsync/install/index.php"
  "elixir.reviewsync/install/tools/sync.php"
  "elixir.reviewsync/lib/Service/ReviewSyncService.php"
  "elixir.delivery/include.php"
  "elixir.delivery/install/index.php"
  "elixir.delivery/install/tools/quote.php"
  "elixir.delivery/lib/Service/DeliveryQuoteService.php"
  "deploy/install_delivery.php"
  "deploy/configure_delivery_env.py"
  "elixir.sitebridge/local/api/app_integration.php"
  "elixir.sitebridge/local/api/giveaways.php"
)

for relative_path in "${required_files[@]}"; do
  if [[ ! -f "$SCRIPT_DIR/$relative_path" ]]; then
    echo "MISSING:$relative_path"
    exit 1
  fi
done

if find "$SCRIPT_DIR/elixir.promo" "$SCRIPT_DIR/elixir.reviewsync" "$SCRIPT_DIR/elixir.delivery" "$SCRIPT_DIR/elixir.sitebridge" "$SCRIPT_DIR/deploy" \
  \( -name '.DS_Store' -o -name '__MACOSX' -o -name '._*' \) -print | grep -q .; then
  echo "ERROR:macOS metadata found"
  exit 1
fi

if grep -R -n -E \
  "(token|shared_secret)[[:space:]]*=>[[:space:]]*'[^']{32,}'" \
  "$SCRIPT_DIR/elixir.promo" "$SCRIPT_DIR/elixir.reviewsync" "$SCRIPT_DIR/elixir.delivery" "$SCRIPT_DIR/elixir.sitebridge"; then
  echo "ERROR:possible embedded secret found"
  exit 1
fi

if find "$SCRIPT_DIR/elixir.promo" -type f -name '*reconcile*' -print | grep -q .; then
  echo "ERROR:public promo reconciliation artifact found"
  exit 1
fi

if command -v php >/dev/null 2>&1; then
  while IFS= read -r -d '' php_file; do
    php -l "$php_file" >/dev/null
  done < <(
    find "$SCRIPT_DIR/elixir.promo" "$SCRIPT_DIR/elixir.reviewsync" "$SCRIPT_DIR/elixir.delivery" "$SCRIPT_DIR/elixir.sitebridge" "$SCRIPT_DIR/deploy" \
      -type f -name '*.php' -print0
  )
  echo "PHP_LINT:OK"
else
  echo "PHP_LINT:SKIPPED (php is not installed locally)"
fi

echo "STRUCTURE:OK"
