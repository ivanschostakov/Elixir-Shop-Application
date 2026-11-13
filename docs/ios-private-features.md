# Private iOS access

The iOS Mentor and Community are not available to public customer accounts.
Android access and the standard AI and support chats are unchanged. The store
catalog is controlled separately.

Provision the single app-only customer in the deployed API environment:

```sh
python -m src.scripts.bootstrap_ios_private_features owner@example.com
```

The script refuses to overwrite existing customers or staff. Set
`IOS_PRIVATE_FEATURES_USER_ID` to the returned customer ID for the API and
notification worker. Use **Forgot password?** with that email to set the first
password, then sign in as `admin` or with the email. Sign-in email verification
is required; the customer has no staff permissions or website identity.

The server skips only iOS App Attest for the configured active and verified
customer. Other iOS customers and Android verification are unaffected. Reset
the configured ID to `0` to remove access, or disable the customer and revoke
their sessions to retire the account. Keep the account private and separate
from App Review credentials.
