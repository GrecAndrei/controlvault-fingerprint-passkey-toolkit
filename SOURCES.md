# Source provenance

This bundle was assembled from the locally validated deployments on 2026-09-06 (Europe/Bucharest):

| Component | Source revision |
| --- | --- |
| Passless + TPM/fingerprint profile | `eac817c` in the local `hello-passkey` checkout |
| ControlVault host-event shim | `044276be433957a5e209a7b3ee68b7ee78d492cc` |
| ControlVault firmware controller | `c8cca3ff655283b5ce0d58635b4bc2bab8f9d128` |

The deployment used Broadcom TOD 5.15.021.0, libfprint-tod 1.95.2, and a Dell Latitude 7400 reader identified as USB `0a5c:5843`. Proprietary driver/firmware payloads, TPM state, enrolled biometric data, and machine-specific logs are intentionally not part of this repository.
