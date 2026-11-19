# App Review customer access

Apple Review uses the reserved customer username `app-review`, never an admin-panel
login. The login code checks that username directly, with no environment flag,
customer-ID override or email override.

Only the email OTP step is skipped. The existing account must be active and verified,
and the password must be valid. Rate limits, normal customer permissions, consent
requirements and mandatory device verification apply. No extra features are unlocked.
Other customers, including administrators using the customer app, require email OTP.

## Provision

Run inside the backend environment (password is prompted, never stored in Git):

```sh
python -m src.scripts.bootstrap_app_review app-review@example.com
```

The command creates only the `app-review` username and refuses to overwrite an
existing customer or reuse an administrator email. No environment changes enable
this login exception. Website identity synchronization cannot overwrite the reserved
customer's credentials.

Provide the username and password in App Store Connect's App Review Information.
Verify that a valid password returns ordinary customer tokens, an incorrect password
returns 401, and device verification remains mandatory for protected operations.

## Disable or rotate

Disable the customer and revoke its sessions to withdraw access. To rotate access,
change the password, revoke existing sessions, and update App Review Information.
Do not reassign the reserved `app-review` username to another customer.
