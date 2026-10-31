# Release lanes: dev, canary and main

## Status and precedence

Merging this file adopts only three things: the impact classification (section
3), the catch rules (section 4) and the lane-decision trail (section 7). They
add checks and grant no authority.

Everything marked PROPOSED is not adopted. Each widening comes later as its own
PR under PRINCIPLES.md section 3 (Earned autonomy): one agent or one project,
with evidence, a time or milestone limit and an undo path. A hard-limit class
first needs the section 11 step 3 control, run with the Owner still gating.

Precedence, highest first: PRINCIPLES.md, then Colony, then this file.

## 1. Sources

Core philosophy: the Colony working method ("Colony workflow and measurement
handoff", 30 Oct 2026). This file depends on these Colony rules only:

- "Feature/integration-to-release is permitted within the existing scope;
  release-to-main remains human-only."
- "No unauthorized deployment, production upload, credentials, security/access
  changes or financial execution."
- Maturity L3, falsifiable verification: "Acceptance is tested against
  observable results."
- Maturity L6, gates and recovery paths: "Authority/risk rules govern
  transitions and failures return only to affected nodes."
- Maturity L7, learning across layers: "A lesson changes the appropriate tool,
  memory, check or workflow ... A prompt edit or written lesson alone is
  insufficient."

Colony has no installed runtime maturity assessor yet, so no project can show
L6 at runtime today.

The Owner's stated intent (30 Oct 2026) is that once a project has launched,
the merge to main is the only human gate, unless spending goes past the
delegated budget. That is not yet in PRINCIPLES.md, so it grants nothing.
Hard limits 2, 4, 5 and 6 (credentials, sends, deletes, irreversible) would
still apply.

Supporting inspiration, not authority:

- [jsnnsa, "How I Built the Most AI-Pilled Company in the World"](https://x.com/jsnnsa/status/2115623382721126826):
  agents coordinate through shared code and the live product, and keep a few
  hard gates only where undo is impossible.
- [0xjmori, "Grok Bot Agents: How to Build an AI Team You Can Actually Trust"](https://x.com/0xjmori/status/2101661510091034926):
  autonomy is earned by clean runs and lowered when quality drops.
- [m4lkxx, "Harness, Loops, Graphs"](https://x.com/m4lkxx/status/2114338456750997922):
  gate on the price of undo; the model labels a change and code decides what
  the label unlocks.

## 2. Lanes

| Lane | What it is | Use it for |
| --- | --- | --- |
| dev | Feature or integration branch on the dev overlay | Anything unproven that changes how the app works or integrates |
| canary | Release candidate on a canary overlay with its own data and capped real traffic | Soak, small fixes, A/B tests |
| main | Release PR merged to main by the Owner, then a reviewed pin-bump or overlay PR, merged by the Owner, moves prod to the new pinned commit or digest | Production |

No project has a canary today; the release controller's canary ring waits on an
Owner decision. Until a project has one, its changes go dev then main, using
the dev soak in section 5.

## 3. Impact classification (adopted)

The author scores six factors 0 to 2 and records them in the trail (section 7).

| Factor | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Blast radius | One module, no callers change | One service or its callers | Many services, shared libraries, cluster config |
| Reversibility | `git revert` restores exactly | Revert plus a redeploy or cache flush | Forward-fix only |
| Data / schema | None | Additive (new column, new key) | Changes existing data or contracts |
| Security | None | Input handling or dependencies | (auth and access policy are I4) |
| Cost | No change | Under 20% more run cost | 20% or more, inside the delegated budget |
| User-visible | No | Behind a flag, or cosmetic | Changes default behaviour users rely on |

The highest matching class wins:

| Class | Rule | Minimum lane path |
| --- | --- | --- |
| I4 hard limit | Any auth, access-policy, credential or secret change; any delete; any external send; anything not reversible; spending past the delegated budget | None until the Owner decides (tier C) |
| I3 systemic | Data 2 or Reversibility 2, or a total of 7 or more | dev, then canary (long soak), then main |
| I2 moderate | A total of 4 to 6, or any other factor at 2 | dev, then canary, then main |
| I1 small | Not I0, a total of 3 or less, no factor at 2 | dev or canary, then main |
| I0 trivial | A total of 1 or less, Data 0, Security 0, no path rule fired | The next release PR |

Every class reaches main through the release PR, which the Owner merges.

## 4. Catch rules (adopted)

Path rules can raise a class, never lower it:

- Owner merge whatever the score: `.github/workflows/**`, Makefile and other
  quality-gate targets, CODEOWNERS, `.flux/**`, the classifier rule file, and
  any change that deletes, skips or weakens a test.
- I4: auth and access-policy code and config.
- Data at least 1: migrations. Security at least 1: lockfiles and dependency
  manifests.

Review flow: the author states the class in the PR. Peer Reviewer's review
states the class it finds. If they differ, Peer Reviewer requests changes and
the author relabels to the higher class. A raised class restarts the lane path
and the soak clock for anything already deployed.

PROPOSED: a classifier that applies the path rules as a local gate (Colony has
no feature GitHub Actions). The Chief of Staff would own it and its rule file.
Until it exists, the author and Peer Reviewer apply the rules by hand.

## 5. Soak and promotion signals

The gate that exists today: local gates and CI green, Flux reports Ready and
its health checks pass within the project's rollout deadline, and a read-only
smoke check passes. Prod checks are read-only smoke only, because an
integration suite can write data or send messages.

Minimum soak (adopted with the lane paths, since it only adds waiting):

| Class | dev soak | canary soak (once a canary exists) |
| --- | --- | --- |
| I0 | none | none |
| I1 | 2 h including one load run or one full job cycle | 2 h including one full job cycle |
| I2 | 24 h including a load run | 24 h including the daily peak |
| I3 | 24 h including a load run | 72 h including a weekday peak |

"Daily peak" is the busiest hour of the last 7 days; "weekday peak" is the
same, for weekdays only.

PROPOSED signals. No project has a source for them yet. Each one is adopted
for a project only when the project names its source and owner:

- error rate at most the larger of baseline times 1.2 and baseline plus 0.1
  percentage points, with no new error signature (an error type and code
  location not seen in prod in the last 7 days);
- p95 latency at most the larger of baseline times 1.2 and baseline plus 50 ms;
- run cost per hour at most baseline times 1.2, with a floor of one dollar;
- the product numbers the project names are not down more than 5%.

A missing signal is unknown and never counts as a pass. An error-budget freeze
needs an SLO first: once a project defines one, using more than 50% of the
30-day budget lets only fixes for that budget promote.

## 6. Delegated authority

| Step | Today | PROPOSED |
| --- | --- | --- |
| Deploy to dev or canary | Owner (hard limit 3) | Owner agent, for a project at runtime L6 |
| dev to canary | Owner | Owner agent after Peer Reviewer approves, for a project at runtime L6 |
| Merge into feature, integration or release branches | PRINCIPLES.md section 6: the author merges after Peer Reviewer approves (this wins over Colony's nonauthor integrator) | Unchanged |
| Release PR to main | Owner | Unchanged |
| Move prod (pin-bump or overlay PR) | Owner | Unchanged; release controller auto-merge awaits an Owner answer |
| Roll back prod | Owner-merged PR, tier C (PRINCIPLES.md section 12, step 3) | Automatic, see below |

PROPOSED rollback, which needs the section 11 step 3 control evidence and
amends the tier C in section 12, step 3:

- Triggers: a signal outside threshold for 10 minutes in canary, or for at
  least one alarm check interval in prod; a failed smoke check; a crash loop.
- Windows start once the rollout is Ready or its deadline has passed. A
  project's decided values win (rollout deadline, outside-alarm timing,
  shut-off retry).
- The revert goes to the last known-good pin: the previous pin that passed its
  soak. One promotion per commit, so a revert takes nothing else with it.
- After a migration, an image-only revert is allowed only if expand/contract
  held. Otherwise stop and forward-fix at tier C. The contract (drop) step is
  I4.

PROPOSED A/B tests, once a canary exists: own data store or read-only prod
data, flag off in prod, traffic within the canary cap, no external sends, and a
stop rule with an end date, a named metric and a minimum sample size.

## 7. The lane-decision trail (adopted)

Agents read the trail instead of messaging each other. The knowledge index
indexes it.

- The PR body's Risk and Rollback section states the six scores, the class, the
  lane path, and each lane step with its start, end and result.
- Labels: `impact:I0` to `impact:I4`, and `lane:dev`, `lane:canary` or
  `lane:main`.
- The overlay or pin commit that moved a lane.

Cost today: `tools/turn-cost-ledger` covers Codex turns only, one row per
`(session_id, turn_id)`, with model, tokens and agent wall clock. Cost comes
from `api_equivalent_usd` when present, otherwise from models.dev API rates. A
daily `--since-last-run` run reconciles missed turns. The ledger output stays
private; the tool is public.

PROPOSED ledger extension: a PR and lane-step key, human wall-clock time, and
agents other than Codex.

## 8. Mis-classification

Caught by the path rules, by Peer Reviewer's class check, and by escaped
defects. A merge reverted for a defect is already an incident (PRINCIPLES.md
section 12).

PROPOSED:

- An under-classified change that reached users is an incident for the action
  "promote Ix changes", where Ix is the class it was given.
- Two under-scores caught before merge in 30 days start that agent's changes
  one class higher, until an Owner-merged PR restores it.
- The Chief of Staff runs a weekly review comparing each change's class with
  its outcome. This is separate from the section 11 touchpoint review.

Whichever applies, the fix is a new path rule, a new threshold or a stronger
test, added in the PR that closes the incident record (Colony L7). A note in a
prompt does not count.

## 9. Decision table

| Change | Class | Path |
| --- | --- | --- |
| README fix, new test | I0 | Next release PR |
| Lockfile-only dependency bump | I1 | dev, then main |
| Off-by-one fix in one handler | I1 | dev or canary, then main |
| New feature behind a default-off flag | I2 | dev, then canary, then main |
| Additive DB column with backfill | I3 | dev, then canary (long soak), then main |
| Auth flow change, key rotation, dropped table | I4 | Owner decides first |

## 10. PROPOSED open questions (for the Owner)

- Q2. Should agents deploy to dev and canary? Recommended: yes, one project per
  PR, once it shows runtime L6, with automatic rollback attached.
- Q3. Should a rollback to the last known-good prod pin be pre-approved?
  Recommended: yes, image-only, never with a data migration.
- Q4. Can I1 skip the Owner from canary to main later? Recommended: not yet;
  revisit after 50 I1 promotions with no escaped defect.
- Q5. Are the soak times and thresholds right? Recommended: adopt as written
  and review after the first month of data.
