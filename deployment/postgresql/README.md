# PostgreSQL and the shop Docker bridge

The production PostgreSQL cluster listens on `localhost,172.18.0.1`.
The private bridge must exist before PostgreSQL starts. Otherwise PostgreSQL
can start successfully with only its localhost listener, leaving containers
unable to connect until the cluster is restarted.

Install `10-shop-docker-ordering.conf` under
`/etc/systemd/system/postgresql@18-main.service.d/`, then run
`systemctl daemon-reload`. A PostgreSQL restart is required if the private
listener is already missing. Back up the application database and pause
financial retry workers before maintenance.

Keep the listener private. The existing `pg_hba.conf` rule grants only the
shop database/user access from `172.18.0.0/16` with SCRAM authentication.
Do not replace it with public listening or a trust rule.
