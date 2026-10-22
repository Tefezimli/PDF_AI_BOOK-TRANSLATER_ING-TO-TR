# Security Policy

## Supported Versions

We actively provide security updates and patches for the following versions:

| Version | Supported          | Security Status |
| ------- | ------------------ | --------------- |
| 17.x    | :white_check_mark: | Active Support  |
| 14.x    | :white_check_mark: | Maintenance     |
| < 14.0  | :x:                | Deprecated      |

---

## Security Model & Air-Gapped Privacy

**PDF AI Engine** is designed from the ground up with a **strict offline security architecture**:

1. **Zero External Network Calls:** The engine operates in a 100% air-gapped environment. No documents, plain text, extracted images, or telemetry are ever transmitted over the network.
2. **Local Model Execution:** All neural machine translation (MarianMT) and OCR processes run locally on the host's hardware (GPU / CPU).
3. **Telemetry Lock:** Hugging Face telemetry and token checkers are explicitly disabled programmatically (`HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`).

---

## Reporting a Vulnerability

We take the security of this software and user data privacy very seriously. If you discover a security vulnerability, please report it responsibly:

### 1. Preferred Method: GitHub Private Vulnerability Reporting
Please use GitHub's **[Report a vulnerability](https://github.com/Tefezimli/PDF_AI_BOOK-TRANSLATER_ING-TO-TR/security/advisories/new)** button under the Security tab. This allows us to discuss and patch the issue in private before a public advisory is issued.

### 2. What to Include in Your Report
To help us triage and resolve the issue quickly, please include:
* Description of the vulnerability and its potential impact.
* Step-by-step reproduction instructions or proof-of-concept (PoC).
* Operating System and environment details (Windows version, Python version, CUDA version).

### 3. Response Timelines
* **Initial Response:** Within 48 hours of report receipt.
* **Triage & Assessment:** Within 5 business days.
* **Fix & Release:** As soon as feasible, coordinated with the reporter.

Please do not disclose security issues publicly in GitHub Issues or pull requests until a fix has been released.
