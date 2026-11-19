## What and why
<!-- One or two sentences. Link the issue if there is one. -->

## How it was verified
- [ ] `make lint` and `make test` pass
- [ ] `make test-pg` passes (if the change touches the database, queue, cache or leader code)
- [ ] Ran the real thing (browser / `make smoke`) and looked at it, not only unit tests
- [ ] Added or updated a test that fails without this change

## Checklist
- [ ] Migration included and safe for the previous release (expand, then contract)
- [ ] No per-process state another replica would need; any cache holds only user-independent data
- [ ] New endpoint has auth and, if it costs CPU or money, a rate limit
- [ ] Docs updated (`make docs` if routes changed); anything not verified is said plainly
