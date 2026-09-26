"""Security layer: input guarding, secret detection, tamper-evident audit."""

from harness.security.audit import AuditLog
from harness.security.input_guard import (
    detect_prompt_injection,
    sanitize_path,
    validate_command,
)
from harness.security.secret_scanner import (
    Finding,
    check_path_policy,
    scan_diff,
    scan_path,
    scan_text,
)

__all__ = [
    "AuditLog",
    "Finding",
    "check_path_policy",
    "detect_prompt_injection",
    "sanitize_path",
    "scan_diff",
    "scan_path",
    "scan_text",
    "validate_command",
]
