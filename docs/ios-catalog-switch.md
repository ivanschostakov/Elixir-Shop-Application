# iOS release scope and updates

The iOS release includes the catalog and checkout, AI chat, Mentor, Community,
profile, order history and support. These features use the same access policy
for ordinary customers and the App Review demo customer. Standard sign-in,
consent, device verification and product visibility restrictions still apply.

The full published catalog is available to all platforms, guests and customers.
Archived or unpublished products remain unavailable. There are no category scopes
selected by account, platform or environment, and no review-mode commerce switch.

Companion and Community are fixed parts of this release. Mentor accepts protocol 2
only; older companion requests receive HTTP 426 and must update. Nutrition rules
and the current consent version are defined in code. Consent and confirmation are
still required. The profile always shows the authoritative MoySklad account view.
MoySklad order synchronization, settlement-balance accounting, balance checkout,
Telegram user-session synchronization is fixed on. Yandex delivery points are
temporarily disabled in code, without an environment override.
Provider credentials, authorized Telegram sessions and the standard financial
validation are still required; no external services were deployed by this change.

iOS entitlements derive the App Attest environment from the Xcode configuration:
Debug uses development and Release uses production. The release API accepts only
production attestations, without an environment override.

The application does not download or execute replacement application code.
The OTA client dependency, update service URL, runtime targeting, EAS channels
and JavaScript-bundle version gate have been removed. `updates.enabled` is false.
The version endpoint contains only installed store-build versions and store links.
Updating application code requires a new App Store or Google Play submission.

Before the next submission:

1. Run frontend type checking, regression tests and the backend access-policy tests.
2. Confirm the effective Expo config disables updates and has no update URL/runtime.
3. Confirm release autolinking excludes the OTA client module.
4. Create a new store binary and verify its contents; configuration checks alone
   do not verify the contents of a previously submitted binary.
5. Give App Review a working demo login and disclose navigation to all features.

The current changes do not modify an already-uploaded binary. No new binary was
built or submitted while preparing this change, and no backend was deployed.
