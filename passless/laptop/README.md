# Latitude local passkey store

This profile turns Passless into a browser-visible CTAP2 authenticator using
Linux UHID. Discoverable credentials (passkeys) are stored under
`~/.local/share/passless/tpm`; every credential blob is encrypted and sealed to
this laptop's TPM 2.0. Browser registration and authentication require a
successful scan of the enrolled fingerprint through fprintd.

Install from a clean checkout:

```sh
./laptop/install.sh
```

Confirm the service and virtual authenticator:

```sh
systemctl --user status passless.service
passless client list
```

Chromium and Firefox installed as native packages can use it anywhere a site
offers “security key” or “passkey on this device.” Sandboxed Flatpak/Snap
browsers may not have access to the generated hidraw node.

## Security properties

- User service; it does not run as root.
- Credential files are mode 0600 beneath a mode 0700 directory.
- Credentials are AES-GCM encrypted with a key sealed to the device TPM.
- User verification is mandatory and credential export is disabled.
- Fingerprint verification is fail-closed: an unavailable sensor, non-match,
  or 45-second timeout denies the ceremony. It never falls back to a desktop
  notification for verification. (A notification may still be used separately
  for CTAP user-presence consent.)
- Core dumps are disabled and sensitive memory is locked.
- The service has no Internet socket access.

The legacy device-bound TPM backend unseals a credential into the hardened
daemon when it signs. It is stronger than plaintext software storage, but not
equivalent to a certified hardware security key or Windows Hello hardware
attestation. The optional portable TPM backend keeps signing keys inside the
TPM, but is experimental on physical TPMs and requires careful recovery-seed
handling, so this profile does not enable it by default.

Do not use this as the only authenticator for an important account until a
recovery method or second hardware key is registered.
