# v0.4.2 Experimental Changelog

- Added issuer-controlled constraint binding metadata (`binds_to`, `parameter_type`, `unit`).
- Delegation attenuation rejects changes to binding metadata.
- Authorization engine checks commanded canonical-action parameters against bound grant constraints.
- Added signed runtime physical envelope to Tier 3 receipts.
- Added independent simulated measured-force enforcement at actuator boundary.
- Added authenticated revocation epoch heartbeat and deployment freshness bound Δ=0.5 s.
- Moved revocation freshness enforcement to physical RELEASE at actuator-adjacent boundary.
- Distinguished RELEASE (physical effect) from COMMIT (consumption accounting).
- Added illustrative safe-state transfer for revocation during active motion.
- Retained fail-closed non-SINGLE consumption and added adversarial coverage.
- Updated claim matrix to classify these changes as engineering/specification requirements, not novelty claims.
