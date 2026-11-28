# MoySklad checkout handoff

New app orders carry `ms_checkout_version: 2` in their checkout snapshot. Previously
created orders keep their original export protocol. No data migration is needed.

| Warm reference data, known buyer, no new promo or balance use | Synchronous calls to MS |
| --- | --- |
| Accept an order for manager payment | POST customer order, GET order with positions to verify the reserve |
| Accept an SBP order with an existing, fully expanded invoice and return the QR | The two calls above, then one fresh GET of the order with stock and its invoice before contacting the gateway |

These are best-case counts, not an order-wide rate limit. Cold references,
unlinked customers, settlement, missing invoice details and recovery need more
reads. Writing the "invoice sent" status runs separately. Product availability,
financial documents, consent and payment authorization are never reused between
payment attempts.

The app persists the send intent before an order or invoice POST. After a lost
reply it searches for the same external code and checks the linked order, buyer
and amount. If the document cannot be found, reconcile the existing order; do
not erase the intent or manually create a replacement without checking MS.
An explicit rejection such as HTTP 429 permits a subsequent attempt. A single
durable job waits for a settlement invoice; it does not create a gateway payment.
Never start a real charge to smoke-test a release.
