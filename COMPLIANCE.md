# Compliance Posture

- **Cryptography**: SDK interfaces exclusively with QBitFlow services for regulated cryptographic operations. No custom crypto primitives are implemented in the SDK.
- **Regulatory**: Designed to aid compliance with AML/CFT, sanctions screening, and transaction monitoring through server-side services.
- **Data**: PII handling guidance provided in docs; SDK minimizes on-device sensitive data retention.
- **Logging**: Configurable privacy-preserving logs; redaction defaults enabled.
- **Conformance**: A public test suite validates protocol and security requirements to qualify for “Compatible with QBitFlow” status.
