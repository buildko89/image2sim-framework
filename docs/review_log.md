# Review Log

This project proceeds by integrating reviews from ChatGPT, Claude, Gemini, Codex, and the user.

## Review Format

Each review entry must use this format:

```markdown
### REV-YYYYMMDD-XXX: Title

- Reviewer: ChatGPT | Claude | Gemini | User | Codex
- Date: YYYY-MM-DD
- Target:
- Summary:
- Findings:
  - [High]
  - [Medium]
  - [Low]
- Actions:
  - Accepted:
  - Deferred:
  - Rejected:
- Related Decisions:
```

## Review Entries

### REV-20260528-001: Initial multi-agent review policy

- Reviewer: ChatGPT
- Date: 2026-05-28
- Target: MVP roadmap and project governance
- Summary: ChatGPT acts as PM and architect, organizing MVP scope, roadmap, risk, and adoption decisions across reviews.
- Findings:
  - [High] Review findings and adoption decisions need durable docs to avoid scattered context.
  - [Medium] MVP scope must stay separate from future framework ideas.
  - [Low] Task templates can reduce ambiguity between implementation turns.
- Actions:
  - Accepted: Use `docs/review_log.md`, `docs/decisions.md`, and `docs/backlog.md` as the operational records.
  - Deferred: Detailed GitHub Issue and PR rules remain for a later documentation task if needed.
  - Rejected: None.
- Related Decisions: DEC-20260528-001, DEC-20260528-002

### REV-20260528-002: Claude specification review summary

- Reviewer: Claude
- Date: 2026-05-28
- Target: Initial project specification
- Summary: Claude reviewed the specification and emphasized task separation, metadata handling, and consistency across directories and docs.
- Findings:
  - [High] Task 0.5 should be separated from Task 0 because API and Blender verification can introduce environment-specific complexity.
  - [Medium] Task 1 and Task 1.5 should remain separate so inventory generation does not mix with subjective image selection.
  - [Medium] Metadata and directory naming need to stay consistent as scripts are added.
  - [Low] Documentation should explicitly record assumptions and open decisions.
- Actions:
  - Accepted: Keep Task 0.5, Task 1, and Task 1.5 as separate backlog items.
  - Deferred: Metadata schema details will be handled when Task 1 is implemented.
  - Rejected: None.
- Related Decisions: DEC-20260528-005

### REV-20260528-003: Gemini implementation and tooling review summary

- Reviewer: Gemini
- Date: 2026-05-28
- Target: 3D generation and processing plan
- Summary: Gemini highlighted provider choice, image masking risks, Blender normalization concerns, and Windows/WSL2/Blender CLI boundaries.
- Findings:
  - [High] Windows, WSL2, Docker, and Blender CLI boundaries should be decided before automation scripts depend on paths.
  - [Medium] Tripo priority, Quad output, and retopology options should be verified before deeper pipeline work.
  - [Medium] `rembg` may create shadow or edge artifacts and needs review outputs.
  - [Low] Blender cleanup should consider foot-origin placement and Unity axis settings.
- Actions:
  - Accepted: Resolve runtime and Blender CLI policy in Task 0.5.
  - Deferred: `rembg`, Quad/Retopo validation, and foot-origin cleanup are deferred to later implementation tasks.
  - Rejected: None.
- Related Decisions: DEC-20260528-003, DEC-20260528-004, DEC-20260528-005

### REV-20260621-004: Codex Task 2 implementation review

- Reviewer: Codex
- Date: 2026-06-21
- Target: Task 2 background removal implementation
- Summary: Implemented a local background removal step that keeps generated image artifacts outside Git and records reviewable mask metrics.
- Findings:
  - [High] Background removal output must be manually reviewed before 3D generation because edge artifacts and missing foreground can damage downstream geometry.
  - [Medium] ONNX model download and runtime performance depend on the local machine and cache state.
  - [Low] Foreground coverage warnings are a lightweight smoke check, not a semantic quality score.
- Actions:
  - Accepted: Add transparent cutouts, alpha masks, checkerboard review images, and JSON/CSV reports.
  - Deferred: Automatic semantic mask scoring and alternate background removal providers remain future work.
  - Rejected: Calling 3D generation APIs during Task 2.
- Related Decisions: DEC-20260621-008

### REV-20260621-005: Codex Task 3 prototype review

- Reviewer: Codex
- Date: 2026-06-21
- Target: Task 3 Tripo Image-to-3D prototype
- Summary: Added a Tripo prototype script with dry-run by default, explicit submit mode, raw API response capture, polling support, and optional output download.
- Findings:
  - [High] Real API submission can consume credits, so it must require an explicit `--submit`.
  - [Medium] Tripo output URLs expire quickly, so raw responses and optional downloads need to be captured immediately after success.
  - [Low] The first prototype handles single-image Image-to-Model only; multiview generation remains out of scope until single-image flow is proven.
- Actions:
  - Accepted: Add dry-run request planning, upload/create/poll flow, raw response files, and normalized report output.
  - Deferred: Multi-image Tripo generation, streaming progress, and provider abstraction.
  - Rejected: Automatically submitting API jobs during smoke checks.
- Related Decisions: DEC-20260621-009
