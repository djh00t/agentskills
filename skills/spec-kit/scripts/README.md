# scripts

Deterministic executable helpers for the `spec-kit` skill.

## Included

- `spec_kit_plan.py`: builds deterministic task ordering and parallel groups
  from skill input JSON, with `request_type` support for `new-feature` or
  `behavior-change`.
- `spec_kit_emit_issues.py`: emits deterministic `gh issue create` commands,
  and can publish only with explicit approval.
- `install_spec_kit_deps.sh`: installs `uv` if needed and installs upstream
  Spec-Kit CLI (`specify`) from GitHub.

## Example

```bash
python skills/spec-kit/scripts/spec_kit_plan.py \
  --input skills/spec-kit/examples/input_spec.json \
  --output /tmp/spec_kit_plan.json \
  --request-type behavior-change

python skills/spec-kit/scripts/spec_kit_emit_issues.py \
  --plan /tmp/spec_kit_plan.json \
  --output /tmp/spec_kit_issue_emission.json \
  --repo djh00t/agentskills

bash skills/spec-kit/scripts/install_spec_kit_deps.sh
```
