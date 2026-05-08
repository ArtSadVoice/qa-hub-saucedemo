<!--
PR template — keep it lightweight. Delete sections that don't apply.
For the smoke-test policy, see docs/SMOKE_TEST.md.
-->

## Summary

<!-- 1–3 bullets. What changed and why? Link the issue/incident if any. -->

-

## Test plan

- [ ] CI green (pytest + vue-build + structure-check)
- [ ] Smoke tested **OR** N/A because: <!-- e.g. pure refactor, docs only, backend module fully covered by unit tests -->

<!--
Smoke is required for: UI changes, new API + UI integration, cross-system
flows (preflight gate, sync, redirects), scaffold updates that affect
downstream projects. See docs/SMOKE_TEST.md for the decision tree + how-to.
-->

### If smoke tested — fill these

- [ ] Started a test server on a free port (didn't disrupt the running master instance)
- [ ] Walked the happy path in the browser **and** at least one failure path
- [ ] Screenshot / short recording attached below for any UI change
- [ ] Cleaned up test artifacts (fake locks, mock data) after the run

<details>
<summary>Smoke evidence</summary>

<!-- Paste screenshot(s) or a short Loom/asciinema link. Drag-drop into GitHub
     to upload. For backend-only flows, paste curl output. -->

</details>

## Notes for review

<!-- Anything reviewers should know that isn't in the diff: trade-offs you
     considered, deferred follow-ups, why a particular file is touched but
     looks unrelated, etc. -->

-
