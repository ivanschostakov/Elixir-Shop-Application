# App Review customer access

Apple Review uses a dedicated **customer** identity, never an admin-panel login.
Only its email OTP is skipped. A valid password, active/verified account, normal
rate limits, customer permissions and device-integrity checks still apply.
The account uses normal application features and loyalty rules.

## Provision and enable

Run inside the backend environment (password is prompted, not stored in Git):

```sh
python -m src.scripts.bootstrap_app_review app-review@example.com --username app-review
```

The command refuses to overwrite an existing customer or reuse an admin email.
Save its printed `AUTH_APP_REVIEW_USER_ID` and `AUTH_APP_REVIEW_EMAIL` values in
the production `backend/.env`, then recreate only `backend-api`. Both values
must match the same customer; the default ID `0` disables the exception.
The review customer authenticates locally, not through Bitrix website login.

Provide the username and password in App Store Connect's App Review Information.
Verify `/api/v1/auth/login` returns customer tokens without
`verification_required`, a wrong password returns 401, and the same credentials
cannot sign into the admin panel. Do not store the password in this document.

## Disable or rotate

- Set `AUTH_APP_REVIEW_USER_ID=0` and recreate `backend-api` to restore OTP.
- Disabling the customer prevents new login; revoke its sessions too when
  withdrawing access. OTP configuration alone does not revoke existing tokens.
- Rotate the customer password and revoke its sessions before sharing replacement
  credentials. Update App Review Information with the new password.
- Deleting and re-registering the same email does **not** inherit the exception:
  the newly created customer has a different ID.

No Bitrix website files, admin identities or public registration rules are changed.
