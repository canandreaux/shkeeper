# Payout callbacks

With `ENABLE_PAYOUT_CALLBACK` enabled, the payout callback job runs every 60
seconds. It queues failed payouts with a nonempty callback URL and no existing
`Payout` notification. This includes older records and status changes committed
directly to the database. Deploying this feature therefore also queues previously
unnotified failures; it does not retry or send the withdrawal itself.

Failure callbacks preserve `payout_id`, `external_id`, `amount`, `crypto`,
`currency_fiat`, and `timestamp`. They send `status: "FAIL"`, `error` from the
payout record, and `tx_hash: null` when no transaction exists. `amount_fiat` is
null for failures so delivery does not depend on exchange-rate availability.
Successful payout payloads remain unchanged.

HTTP 200 or 202 acknowledges delivery. Other responses and network errors use
the existing bounded retry schedule (`REQUESTS_NOTIFICATION_RETRIES`, default
10). The database's unique `(type, object_id)` constraint prevents duplicate
notification records. Receivers must still handle repeated HTTP deliveries
idempotently, since an acknowledgement can be lost.

This feature reports the stored payout status; it does not independently prove
that a transfer was never broadcast. Do not mark uncertain RPC results as `FAIL`
or automatically refund solely on that assumption. Reconcile uncertain transfers
with the backend and chain first. Changing a previously notified payout's status
does not create another notification; retrying a withdrawal is a separate flow.
