# scripts

Non-Python helper scripts for the `spec-kit` skill.

## Included

- `install_spec_kit_deps.sh`: installs `uv` if needed and installs upstream
  Spec-Kit CLI (`specify`) from GitHub.

Canonical script runtime logic lives in
`src/agentskills/skills/spec_kit/script_entrypoints.py` and is invoked via
the module CLI `python -m agentskills.skills.spec_kit`.

## Example

```bash
python -m agentskills.skills.spec_kit plan \
  --input skills/spec-kit/examples/input_spec.json \
  --output /tmp/spec_kit_plan.json \
  --request-type behavior-change

python -m agentskills.skills.spec_kit emit \
  --plan /tmp/spec_kit_plan.json \
  --output /tmp/spec_kit_issue_emission.json \
  --repo djh00t/agentskills

bash skills/spec-kit/scripts/install_spec_kit_deps.sh
```
