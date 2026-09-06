//! fprintd-backed local user verification.
//!
//! `fprintd-verify` talks to the system fprintd D-Bus service.  Keeping that
//! protocol handling in fprintd means this authenticator never receives a
//! biometric image or template: it receives only the process exit status.

use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const FPRINTD_VERIFY: &str = "/usr/bin/fprintd-verify";
const POLL_INTERVAL: Duration = Duration::from_millis(100);

#[derive(Debug, PartialEq, Eq)]
pub enum FingerprintVerification {
    Matched,
    Rejected(String),
}

/// Request a fingerprint verification from fprintd.
///
/// A zero timeout deliberately means no timeout, matching Passless's existing
/// notification setting.  Any non-zero exit status is a denial, including a
/// missing device or a non-matching fingerprint.  This fail-closed behavior is
/// important: callers must not turn a scanner failure into notification-only UV.
pub fn verify_fingerprint(timeout_secs: u32) -> FingerprintVerification {
    verify_with_command(FPRINTD_VERIFY, timeout_secs)
}

fn verify_with_command(program: &str, timeout_secs: u32) -> FingerprintVerification {
    let mut child = match Command::new(program)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        Ok(child) => child,
        Err(error) => {
            return FingerprintVerification::Rejected(format!("could not start fprintd: {error}"));
        }
    };

    let deadline =
        (timeout_secs != 0).then(|| Instant::now() + Duration::from_secs(timeout_secs as u64));
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return FingerprintVerification::Matched,
            Ok(Some(status)) => {
                return FingerprintVerification::Rejected(format!(
                    "fprintd rejected verification ({status})"
                ));
            }
            Ok(None) => {}
            Err(error) => {
                return FingerprintVerification::Rejected(format!(
                    "could not wait for fprintd: {error}"
                ));
            }
        }

        if deadline.is_some_and(|limit| Instant::now() >= limit) {
            if let Err(error) = child.kill() {
                if error.kind() != std::io::ErrorKind::InvalidInput {
                    return FingerprintVerification::Rejected(format!(
                        "fingerprint timeout and could not stop fprintd: {error}"
                    ));
                }
            }
            let _ = child.wait();
            return FingerprintVerification::Rejected(
                "fingerprint verification timed out".to_string(),
            );
        }
        thread::sleep(POLL_INTERVAL);
    }
}

#[cfg(test)]
mod tests {
    use super::{FingerprintVerification, verify_with_command};

    #[test]
    fn successful_command_matches() {
        assert_eq!(
            verify_with_command("/usr/bin/true", 1),
            FingerprintVerification::Matched
        );
    }

    #[test]
    fn failed_command_is_denied() {
        assert!(matches!(
            verify_with_command("/usr/bin/false", 1),
            FingerprintVerification::Rejected(_)
        ));
    }

    #[test]
    fn missing_command_is_denied() {
        assert!(matches!(
            verify_with_command("/definitely/not/fprintd", 1),
            FingerprintVerification::Rejected(_)
        ));
    }
}
