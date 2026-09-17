# Production release evidence — 2026-09-17

This directory preserves the JSON extracted without reserialization from GitHub Actions artifact `10484512240`, downloaded and verified on 2026-09-17. It is historical runtime evidence, not a claim of continuous availability.

- Run: https://github.com/paslaycorp/FAP-Insurance/actions/runs/34962257479/attempts/4
- Job: https://github.com/paslaycorp/FAP-Insurance/actions/runs/34962257479/job/105107938075
- Artifact: https://github.com/paslaycorp/FAP-Insurance/actions/runs/34962257479/artifacts/10484512240
- Original ZIP SHA-256 (matches GitHub artifact digest): `4d4458db128f6a51969fe787c81bda2a5954259c7f0043f23a5ab649408ed48d`
- Artifact expiry reported by GitHub: 2026-12-16T07:01:09Z
- Release SHA: `3fac573ed2b40f328cbf4325f08bf9645e1babcf`
- EPM pin: `bb0559ddb8eff7f78acc432c0334ce7596c1045c`
- Render deployment: `dep-dalp0hoae00c73c5lk70`

The JSON reports `result=verified`, `render_status=live`, `epm-engine/0.1.2`, matching runtime Git identity, `fap_core_connected=true`, and no rollback. This records attempt 4, not the earlier successful attempt 2. The previously recorded attempt-2 artifact returned 404 during retrieval; no replacement or reconstruction of its original bytes is claimed.

The ZIP digest above is not the digest of the extracted JSON. This record does not establish the root cause or permanent resolution of the earlier HTTP 429. No release gate or assurance semantics are changed.
