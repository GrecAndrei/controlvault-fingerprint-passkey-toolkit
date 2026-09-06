# Fingerprint Passkey Toolkit for Broadcom ControlVault 3

Reproducible Linux tooling for Dell Latitude systems with a Broadcom ControlVault 3 fingerprint reader (`0a5c:5843`). This repository collects the working host-event compatibility shim, safe firmware inspection/controller tools, and a TPM-backed local WebAuthn/CTAP2 passkey store with fail-closed fingerprint user verification.

## What this solves

Some ControlVault 3 readers stop enrolling or verifying because the Linux TOD stack does not handle the device's host-timestamp interrupt. The shim restores that protocol step without touching biometric payloads. The passkey profile then requires a successful `fprintd-verify` match before the virtual FIDO authenticator releases user verification.

## Components

- [`broadcom-host-event-shim/`](broadcom-host-event-shim/) — source-built libusb interposer, tests, installer, rollback, and validation notes. It handles only interrupt type 5 and logs integer status metadata; it never stores fingerprint images or templates.
- [`controlvault3-tools/`](controlvault3-tools/) — read-only USB/protocol probes and a conservative firmware controller. It inventories versions, validates signed bundle structure, compares AAI/SBI releases, and synchronizes the host clock. Raw firmware flashing is intentionally unavailable because an invalid or interrupted update can permanently brick the security controller.
- [`passless/`](passless/) — the Passless Rust authenticator with the local laptop profile, TPM storage, UHID setup, systemd unit, and fail-closed `fprintd` user-verification integration.

## Quick start

1. Install the vendor TOD/libfprint packages appropriate for the reader.
2. Build and install the host-event shim:

   ```sh
   cd broadcom-host-event-shim
   make clean check
   sudo make install
   ```

3. Enroll and verify with the standard fprintd tools:

   ```sh
   fprintd-enroll -f right-index-finger "$USER"
   fprintd-verify -f right-index-finger "$USER"
   ```

4. Install the TPM-backed passkey profile:

   ```sh
   cd passless/laptop
   ./install.sh
   ```

The profile enables `fingerprint_verification = true`. Non-match, timeout, unavailable sensor, and helper errors deny user verification; no notification fallback is used. CTAP user-presence consent remains a separate policy step.

The TPM backend warms its parent key and creates/loads one TPM-sealed AES-256-GCM
storage key during service startup. Credential registration then performs only local
authenticated encryption and an atomic `0600` file write, keeping the CTAP response
inside Chromium's request deadline. The sealed key is stored as
`~/.local/share/passless/tpm/storage_key.tpm`; it is machine-local state and must not
be copied into source control or shared with another TPM.

## Reproducibility and safety

- No captured biometric data, enrollment templates, TPM material, private keys, or host configuration are included.
- Proprietary Dell/Broadcom firmware and Windows driver binaries are deliberately omitted. The controller accepts a path to a locally obtained bundle for inspection only.
- Build/test commands and the exact source commits used for the laptop deployment are retained in each component's README and history.
- The reference deployment was validated with three consecutive right-index matches on a Dell Latitude 7400 after installing the shim.

## Scope

This is a compatibility and integration toolkit, not replacement firmware and not a bypass around biometric or WebAuthn policy. Use the firmware controller in inventory/plan/sync-clock modes only unless you have independently audited the hardware and signed update process.

## License

This repository is licensed under **GPL-3.0-or-later**; see [`LICENSE`](LICENSE).
The bundled Passless component retains its GPLv3 license text in
[`passless/LICENSE`](passless/LICENSE). Source provenance and third-party
attribution are recorded in [`SOURCES.md`](SOURCES.md).
