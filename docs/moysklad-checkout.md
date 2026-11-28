# MoySklad checkout handoff

New app orders carry `ms_checkout_version: 2` in their checkout snapshot. Previously
created orders keep their original export protocol. No data migration is needed.

With `automatic_checkout: true`, creating a basket, saved-draft or guest order
commits the order, local reservation and a single `app:complete-checkout:{order_id}`
job together. Redis wakes the worker; the database is the source of truth if
the notification is lost. Closing the app does not cancel an accepted request.
The phone reads `GET /payments/status` with the order ID and
`automatic_checkout=true`. It never needs a separate "check invoice" action.

| Warm reference data, known buyer, no new promo or balance use | MS calls in the checkout flow |
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
document-preparation job waits for a settlement invoice; that job does not
create a gateway payment. The separate mobile checkout job handles the selected
payment method. Manager acceptance requires a verified reservation and does not
mean the order has been paid. SBP requires verified stock and amounts before
IntellectMoney can receive an invoice request; only confirmed payment is shown as paid.

If the payment provider may have accepted a request but no usable result is
known, do not replay the charge, clear its marker, or start a replacement order.
Check the checkout integration run for that order, the provider transaction and
the linked MS documents. The mobile status `needs_review` is not a customer
retry instruction.
Never start a real charge to smoke-test a release.
