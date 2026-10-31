# Release lanes: dev, canary and main

## Status and precedence

Merging this file adopts:

- the impact classification with its minimum lane path (section 3) and minimum
  soak (section 5), the catch rules (section 4) and the lane-decision trail
  (section 7). These add checks and grant no authority;
- the Q5 soak times and promotion thresholds in section 5, with the additions
  labelled there;
- three time-limited grants, each only within section 6: agent deploys to dev
  and canary (Q2), a prod pin-revert PR (Q3), and I1 release PRs merged by
  their author (Q4).

The Owner answered Q1 to Q5 on 31 Oct 2026 (section 10). A card answer
approves one action only (PRINCIPLES.md section 4), so the grants exist only
as Owner-merged delegations in the colony charter, under PRINCIPLES.md
sections 3 and 4. This PR is paired with the colony PR that adds them. The
grants take effect only when the Owner has merged both.

Everything still marked PROPOSED is not adopted. Each further widening comes
later as its own PR under PRINCIPLES.md section 3 (Earned autonomy): one agent
or one project, with evidence, a time or milestone limit and an undo path. A
hard-limit class first needs the section 11 step 3 control, run with the Owner
still gating.

Precedence, highest first: PRINCIPLES.md, then Colony, then this file.

## 1. Sources

Core philosophy: the Colony working method ("Colony workflow and measurement
handoff", 30 Oct 2026). This file depends on these Colony rules only:

- "Feature/integration-to-release is permitted within the existing scope;
  release-to-main remains human-only." The Q4 grant (section 6) is an
  exception the Owner chose (decision item 21). It is recorded in the colony
  charter as delegation `release-lanes-q4-i1-release-merge`, not by this file.
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
| main | Release PR merged to main (by the Owner, except as section 6 grants), then a reviewed pin-bump or overlay PR, merged by the Owner (except the section 6 Q3 pin-revert), moves prod to the new pinned commit or digest | Production |

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

Every class reaches main through the release PR. Who merges it is in section 6.

The lane paths and soak apply only to deployed projects that have a release
flow and an existing dev deploy path. Other repos record the class and follow
PRINCIPLES.md section 6 only.

## 4. Catch rules (adopted)

Path rules can raise a class, never lower it:

- Owner merge whatever the score: `.github/workflows/**`, Makefile and other
  quality-gate targets, CODEOWNERS, `.flux/**`, the classifier rule file, and
  any change that deletes, skips or weakens a test. One carve-out: the Q3
  pin-revert PR (section 6), whose diff passes the pin-only check, is not
  forced to an Owner merge by the `.flux/**` rule.
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

Minimum soak (adopted with the lane paths, since it only adds waiting). The
Owner's Q5 answer, "A: Adopt as written, review in a month" (decision item 22),
adopted the canary times as listed to the Owner: "I1 2 h, I2 24 h, I3 72 h
including a peak". The canary qualifiers "one full job cycle" (I1), "the daily
peak" (I2) and "a weekday peak" (I3) are Chief of Staff narrowings; they only
add waiting. The dev column is a Chief of Staff addition; it only adds waiting.

| Class | dev soak | canary soak (once a canary exists) |
| --- | --- | --- |
| I0 | none | none |
| I1 | 2 h including one load run or one full job cycle | 2 h including one full job cycle |
| I2 | 24 h including a load run | 24 h including the daily peak |
| I3 | 24 h including a load run | 72 h including a weekday peak |

"Daily peak" is the busiest hour of the last 7 days; "weekday peak" is the
same, for weekdays only.

Promotion signal thresholds (adopted, Q5). No project has a source for them
yet. Each one applies to a project only once the project names its source and
owner:

- error rate at most baseline times 1.2;
- p95 latency at most baseline times 1.2;
- business metrics (the product numbers the project names) are not down more
  than 5%;
- a missing signal is unknown, never counts as a pass, and blocks promotion.

Chief of Staff additions (adopted; each only adds a gate):

- no new error signature (an error type and code location not seen in prod in
  the last 7 days);
- run cost per hour at most baseline times 1.2;
- an error-budget freeze, once a project defines an SLO: using more than 50% of
  the 30-day budget lets only fixes for that budget promote.

PROPOSED floors, which loosen the 1.2 times rule when a baseline is low and so
need their own Owner answer: error rate may also reach baseline plus 0.1
percentage points; p95 may also reach baseline plus 50 ms; run cost may also
reach one dollar per hour.

Review: "review in a month" is the Owner's wording. The computed date, a Chief
of Staff narrowing, is the end of 30 Nov 2026 AEDT (23:59 AEDT).

## 6. Delegated authority

| Step | Today | PROPOSED |
| --- | --- | --- |
| Deploy to dev or canary | Owner (hard limit 3), except the Q2 grant below | Unchanged |
| dev to canary | Owner, except the Q2 grant below | Unchanged |
| Merge into feature, integration or release branches | PRINCIPLES.md section 6: the author merges after a Peer Reviewer APPROVE pinned to the head sha and the rest of the section 6 bar (all required checks green, no changes requested, all feedback resolved). Decision item 74, 3:54 PM AEDT: tapped "74: A", option "A: Author merges after approval (recommended)". Meaning: the author merges after Peer Reviewer approves the exact head sha, as the Owner's own exception to Colony's nonauthor integrator rule. Chief of Staff's narrowing: only feature and fix PRs; release PRs, `.flux` changes, prod changes and authority-changing PRs stay the Owner's merges, except the Q3 and Q4 grants below | Unchanged |
| Release PR to main | Owner, except the Q4 grant below | Unchanged |
| Move prod (pin-bump or overlay PR) | Owner, except the Q3 pin-revert PR below | Unchanged; release controller auto-merge awaits an Owner answer |
| Roll back prod | The Q3 pin-revert PR below. Any other rollback: Owner-merged PR, tier C (PRINCIPLES.md section 12, step 3) | Unattended automatic prod triggers, see below |

### Grants (Q2 to Q4)

Each grant is a colony charter delegation, cited here by id. Common terms:

- Projects: a grant covers only projects named in its colony delegation. The
  Owner named two projects on 31 Oct 2026 (decision item 60, 3:45 PM AEDT); the
  colony delegations list them with their owner agents. Each change under a
  grant covers one project per PR. A further project is added by a PR the
  Owner merges, one project per PR, citing evidence or stating the same accepted evidence gap (PRINCIPLES.md
  section 3, "one agent or one project").
- Expiry: each grant ends at the end of 30 Nov 2026 AEDT (23:59 AEDT), the
  computed Q5 review date, unless a new Owner-merged PR renews it.
- Evidence: none is cited. PRINCIPLES.md section 3 asks for track-record
  evidence and section 11 step 3 control evidence. The Owner accepted the gap
  (decision item 62, 3:45 PM AEDT): "62: yes, accept for the trial until
  30 Nov".
- Undo path: revert or remove the colony delegation, or let it expire. An
  incident in the class drops the agent's tier at once (PRINCIPLES.md section
  12), which suspends that agent's grant.
- Other hard limits stay: the grants do not lift hard limits 1, 2, 4, 5 or 6
  (PRINCIPLES.md section 4: spending, security, credentials and access policy,
  external sends, deletes, anything irreversible). A step that touches one
  stays tier C.

**Q2, deploy to dev and canary** (delegation `release-lanes-q2-dev-canary-deploy`;
decision item 19, 3:17 PM AEDT; answer "A: Level 6 projects only, with
automatic rollback").

- The project's owner agent deploys to dev and canary without asking, only
  for a project at Colony level 6 and only with automatic rollback attached.
- Colony level 6 is the Colony workflow doc's capability maturity level 6,
  "Gates and recovery paths: Authority/risk rules govern transitions and
  failures return only to affected nodes", demonstrated at the runtime stage
  with levels 1 to 6 all currently demonstrated (Colony's rollup rule). Colony
  has no runtime assessor yet, so no project qualifies today.
- Automatic rollback (adopted for dev and canary only): the deploy returns to
  the last known-good pin, the previous pin that passed its soak, without a
  human when a trigger fires. Triggers: a section 5 signal outside threshold
  for 10 minutes; a failed smoke check; a crash loop. Windows start once the
  rollout is Ready or its deadline has passed.
- Fail closed: if no trigger signal has a named source and owner for the
  project, there is no automatic rollback, so no Q2 deploy.
- Chief of Staff narrowing, not the Owner's words: dev to canary also needs a
  Peer Reviewer approval.

**Q3, prod pin-revert PR** (delegation `release-lanes-q3-prod-pin-revert`;
decision item 20, 3:17 PM AEDT; answer "A: Image-only, never with a data
migration").

- The permitted action: the project's owner agent opens and merges a PR whose
  only change sets the prod image pin back to the last known-good image digest.
  Chief of Staff's implementation, not the Owner's words: the PR needs a Peer
  Reviewer APPROVE on its current head, pinned to that sha, and must pass the
  pin-only check.
- Pin-only check: the diff changes only the prod image pin line or lines, and
  the new value equals the last known-good digest recorded in the trail.
  Anything else in the diff, and the `.flux/**` Owner-merge rule applies.
- Last known-good prod pin: the previous prod pin that ran a full alarm window
  with no trigger firing and was not itself rolled back. If the project has no
  defined prod alarm window, no prod pin is known-good, so there is no Q3
  pin-revert.
- Never with a data migration, fail closed: if the trail cannot show that no
  data migration ran since that pin, treat it as having run. Backfills and
  other data-changing jobs count as migrations. Then stop and forward-fix or
  ask, at tier C. The contract (drop) step of a migration is I4.
- Q3 does not cover an incident undo by the agent whose change caused the
  incident: PRINCIPLES.md section 12, Immediate effects step 3, keeps that
  agent's production rollback at tier C. The Owner confirmed this (decision
  item 61, 3:45 PM AEDT): "61: keep it, a different agent rolls back". So the
  project's owner agent may run the pin-revert only when another agent's change
  caused the incident.

**Q4, I1 release PRs to main** (delegation `release-lanes-q4-i1-release-merge`;
decision item 21, 3:18 PM AEDT; question "Can small (I1) fixes reach main
without your approval?"; answer "B: Yes, now").

Chief of Staff's implementation of the Q4 answer (narrows it). The author
merges a release PR whose highest class is I1 only when all of these hold:

- the project is named in the delegation and is in the section 3 scope (a
  deployed project with a release flow and a dev deploy path);
- the PR has passed its section 5 soak;
- Peer Reviewer's APPROVE is recorded on the current head, pinned to that sha,
  and states the class it found as I1;
- all required checks are green and all review feedback is resolved
  (PRINCIPLES.md section 6);
- no catch rule (section 4) forces an Owner merge.

Moving prod stays an Owner merge.

PROPOSED: unattended automatic rollback in prod, using the triggers above with
"for at least one alarm check interval" in place of 10 minutes. It needs the
section 11 step 3 control evidence first. A project's decided values win
(rollout deadline, outside-alarm timing, shut-off retry).

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

## 10. Owner decisions (answered)

All on 31 Oct 2026. The grants take effect only when both this file and the
paired colony charter PR merge (Status, above).

- Q1 (decision item 18, about 2:16 PM AEDT). Should trivial (I0) changes go
  straight to main? A typed reply, "18: C, no". I0 changes ride the next
  release PR (section 3).
- Q2 (decision item 19, 3:17 PM AEDT). Should agents deploy to dev and canary
  without asking? "A: Level 6 projects only, with automatic rollback"
  (section 6).
- Q3 (decision item 20, 3:17 PM AEDT). Should a rollback to the previous prod
  version be pre-approved? "A: Image-only, never with a data migration"
  (section 6).
- Q4 (decision item 21, 3:18 PM AEDT). "Can small (I1) fixes reach main
  without your approval?" "B: Yes, now" (section 6).
- Q5 (decision item 22, 3:19 PM AEDT). Are the soak times and thresholds
  right? "A: Adopt as written, review in a month" (section 5).
- Item 60 (3:45 PM AEDT). Which projects do the grants cover? Two projects,
  listed in the colony delegations (section 6).
- Item 61 (3:45 PM AEDT). May the agent whose change caused an incident roll
  back prod? "61: keep it, a different agent rolls back" (section 6, Q3).
- Item 62 (3:45 PM AEDT). Accept the grants without cited evidence? "62: yes,
  accept for the trial until 30 Nov" (section 6, Evidence).
