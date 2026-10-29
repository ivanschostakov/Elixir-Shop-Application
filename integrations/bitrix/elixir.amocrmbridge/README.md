# Production status synchronization repair

These service files mirror the existing `elixir.amocrmbridge` module on the
COM Bitrix server. This is a targeted update, not a complete module installer.
Back up both installed files and their hashes before replacing them together.

The repair validates order ownership using the module's existing external-code
and order-name helpers before either direction can write data. A stored link
alone is not identity evidence. Foreign links are logged and quarantined from
automatic synchronization; they are not silently relinked or re-exported.

Status export reads the current MoySklad/amoCRM state, avoids identical writes,
blocks automatic backward transitions and fails closed when a state cannot be
read. Explicit cancellation remains available. Queued inbound webhooks use the
current document state rather than a stale state included in an old event.

Run the offline tests with:

```sh
php tests/status_sync_test.php
```

Do not test by moving a real completed order backward. Do not recreate orders,
shipments or payments to fix a status. Existing foreign links require a separate
identity review with the integration owner.
