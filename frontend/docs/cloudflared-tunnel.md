# Elixir Peptide Cloudflare Tunnel

Hostnames:

- `https://elixirshop.devsivanschostakov.org`
- `https://api-elixirshop.devsivanschostakov.org`

Local services:

- frontend web export: `http://127.0.0.1:3000`
- backend API: `http://127.0.0.1:8000`

Run in separate terminals:

```bash
cd /Users/paylakurusyan/Desktop/elixirShopApp
npm run web:export
npm run web:serve:dist
```

```bash
cd /Users/paylakurusyan/Desktop/elixirShopApp
./scripts/run-elixirshop-api.sh
```

```bash
cd /Users/paylakurusyan/Desktop/elixirShopApp
./scripts/run-elixirshop-tunnel.sh
```

Cloudflared config:

- example: `cloudflared/elixirshop.example.yml`
- local: `cloudflared/elixirshop.local.yml`

Notes:

- The frontend uses `https://api-elixirshop.devsivanschostakov.org/api`.
- If you regenerate the web build after frontend changes, rerun `npm run web:export`.
