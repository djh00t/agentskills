# Release lanes: dev, canary and main

Status: proposal. This file widens agent authority, so Peer Reviewer approves it
and only the Owner merges it (PRINCIPLES.md sections 3 and 11). Until then the
current rules apply unchanged. Every rule here sits inside PRINCIPLES.md; where
they conflict, PRINCIPLES.md wins.

## 1. Foundation: Colony

The core philosophy is the Colony working method (Colony workflow and
measurement handoff, 30 Oct 2026) and the Owner's gate policy of the same day:
once a project has launched, **the merge to main is the only human gate**,
unless spending goes past the delegated budget. Everything else is found, built,
reviewed and integrated by agent owners and the swarms they spawn.

This policy uses Colony's words and rules:

- **One accountable owner per outcome**, end to end. Helpers add capacity or
  independent review; a nonauthor integrator integrates.
- **Small packages**: 5–10 minutes, hard cap 15. Push a stable slice when ready.
- **No work registers.** The trail lives in GitHub issues, branches, PRs and
  Flux overlays, indexed by Steve. No new board or approval queue.
- **Separate delivery stages**: source → published → installed → runtime →
  user outcome. Evidence never moves across stages. Merged source is not a
  healthy deployment.
- **Unknown stays unknown.** A missing signal never counts as a pass.
- **Measure benefit, not activity**: accepted outcomes, waiting time, escaped
  defects, recovery, attributable cost, human attention returned.
- **Maturity levels L0–L7** (Colony capability matrix) decide how much a project
  may automate (section 5).

Supporting inspiration (not authority):

- [jsnnsa, "How I Built the Most AI-Pilled Company in the World"](https://x.com/jsnnsa/status/2115623382721126826):
  coordinate through the shared world (stigmergy), hourly ship cadence, full
  suite every 15 minutes on latest, 30-second targeted rollback, dumb hard gates
  only where undo is impossible, ~0.9% revert rate.
- [0xjmori, "Grok Bot Agents: How to Build an AI Team You Can Actually Trust"](https://x.com/0xjmori/status/2101661510091034926):
  autonomy is earned by clean runs and lowered when quality drops; a reviewer
  before more autonomy; bounded loops; weekly audit.
- [m4lkxx, "Harness, Loops, Graphs"](https://x.com/m4lkxx/status/2114338456750997922):
  gate on the price of undo, not on confidence; the model labels the change,
  code decides what the label unlocks; put the human only where undo does not
  exist; a lesson lands on the layer that owns it.

## 2. Lanes

| Lane | What it is | Purpose | Delivery stage |
| --- | --- | --- | --- |
| **dev** | Feature or integration branch, deployed to the cluster's dev overlay | Prove anything unproven that changes how the app works or integrates | source → installed (dev) |
| **canary** | `release/x.y.z` candidate, deployed to the canary overlay with its own data and a capped share of real traffic | Soak, A/B tests, small bug fixes | installed → runtime (canary) |
| **main** | `release/x.y.z` → `main`, then Foreman promotes the image digest to the prod overlay | Production | runtime (prod) → user outcome |

Where a project has no canary overlay yet, canary is skipped and its changes
take the dev → main path with the dev soak times below.

### What each lane must prove before promotion

- **dev → canary**: the new behaviour has a check that failed before and passes
  now (Colony L3); integration suite green on the dev install; no new error
  signatures over the dev soak; migrations ran forward and their rollback or
  forward-fix was exercised.
- **canary → main**: soak time met (section 4); every promotion signal inside
  its threshold; integration suite green on the canary install; the rollback
  path was exercised at least once for this project in the last 30 days.
- **main → prod**: release PR merged by the Owner; Foreman promotion PR passes
  checks and Peer Reviewer approves (unchanged rule); post-deploy smoke and
  integration suite green within 15 minutes.

## 3. Impact classes

The authoring agent scores each change on six factors, 0–2 each. Deterministic
path rules (owned by the classifier, not the agent) can raise a score, never
lower it. Peer Reviewer re-scores in review; the higher score wins.

| Factor | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Blast radius | One module, no callers change | One service or its callers | Many services, shared libs, cluster config |
| Reversibility | `git revert` restores exactly | Revert plus a redeploy or cache flush | Forward-fix only, or not reversible |
| Data / schema | None | Additive (new column, new key) | Changes or deletes existing data or contracts |
| Security | None | Touches auth, input handling or deps | Credentials, access policy, crypto, secrets |
| Cost | No change | Under 20% more run cost, inside budget | Over 20%, or needs budget past delegation |
| User-visible | No | Visible but behind a flag or cosmetic | Changes default behaviour users rely on |

Class is set by the total **and** by any single 2:

| Class | Rule | Examples | Minimum lane path |
| --- | --- | --- | --- |
| **I0 trivial** | Total 0–1, no factor at 2, Data and Security 0 | Docs, comments, tests, typo, log text | main (fast path, section 7) |
| **I1 small** | Total 2–3, no factor at 2 | Local bug fix, small refactor | canary → main |
| **I2 moderate** | Total 4–6, or one 2 outside Data/Security/Reversibility | New feature behind a flag, minor dependency bump | dev → canary → main |
| **I3 systemic** | Total 7+, or a 2 in Data or Reversibility | Schema migration, contract change, infra, auth flow | dev → canary (long soak) → main |
| **I4 hard limit** | Security 2, Cost 2, any delete, external send, or anything irreversible | Credential rotation, destructive migration | Stop: Owner decides before any lane (tier C) |

Path rules that force a class up (examples, kept in code next to the CI check):
`migrations/**` → Data ≥ 1; `.flux/envs/prod/**` → I3 minimum; `**/auth/**`,
`**/secrets/**` → Security ≥ 1; lockfile changes → Security ≥ 1.

## 4. Soak times and promotion signals

| Class | dev soak | canary soak | Canary traffic cap |
| --- | --- | --- | --- |
| I0 | — | — | — |
| I1 | — | 2 h and 500 requests (or one full job cycle) | 10% |
| I2 | integration suite green | 24 h incl. one daily peak | 10% |
| I3 | 24 h | 72 h incl. a weekday peak | 5% |

Promotion signals, each compared with the prod baseline over the same window:

- error rate ≤ baseline × 1.2 (and no new error signature);
- p95 latency ≤ baseline × 1.2;
- zero crash loops or restart storms; health checks green;
- integration suite green on the lane's install;
- run cost per hour ≤ baseline × 1.2;
- product numbers the project names (sign-ups, job success) not down > 5%.

A signal with no data is **unknown**, and unknown blocks promotion (Colony).

**Error budget.** If a service has used more than 50% of its 30-day error budget,
only fixes for that budget promote to main until it recovers.

## 5. Delegated authority

Authority comes from both the impact class and the project's Colony maturity at
the **runtime** stage. Autonomous canary promotion needs demonstrated L6 (gates
and recovery paths); below L6, every canary → main step waits for the Owner.

| Step | I0 | I1 | I2 | I3 |
| --- | --- | --- | --- | --- |
| Deploy to dev | n/a | owner agent | owner agent | owner agent |
| dev → canary | n/a | owner agent after Peer Reviewer approves the PR | owner agent after Peer Reviewer | owner agent after Peer Reviewer, Owner informed |
| canary → main (release PR) | Owner merge (today); fast path proposed | **Owner** | **Owner** | **Owner** |
| main → prod digest | Foreman after Peer Reviewer (unchanged) | same | same | same |
| Roll back a lane | owner agent | owner agent | owner agent | owner agent, Owner told at once |

- Merges into feature, integration and `release/*` branches follow the current
  feature rule: Peer Reviewer approves with no changes requested, checks green,
  a nonauthor integrates.
- Budgets are capped at the delegated amount; going past it is tier C.
- An agent never promotes its own change on its own review. Author ≠ approver.

## 6. Rollback

Automatic rollback fires on any of:

- a promotion signal outside threshold for 10 minutes in canary, 5 minutes in prod;
- post-deploy smoke or integration suite red;
- error-budget burn rate over 10× for 5 minutes;
- a crash loop on the new revision.

**Who:** the lane's owner agent; for prod digests, Foreman. **How:** `git revert`
of the overlay change that promoted the digest, so Flux returns to the last
known-good digest. Code changes are reverted the same way; a fix rides on top
only after the revert is green. I3 changes must use expand/contract migrations
so an image revert never needs a data revert.

Dev and canary rollbacks are tier A. A prod rollback is a live production change
(hard limit 3), so today it is tier C. This policy proposes a pre-approved
control: Foreman may revert a prod digest to the immediately previous digest
with no data migration attached, then report (tier B). **Needs Owner approval.**

## 7. Main fast path for I0 changes

Owner intent: small, non-consequential changes merge straight to main, with a
revert if integration tests fail. Colony keeps release-to-main human-only, so
**Colony wins**: until the Owner changes that rule, I0 changes ride the next
release PR. The proposal, if the Owner approves it:

1. Eligible only if every factor is 0 except at most one 1, and no path rule fires.
2. A PR straight to `main`, ready for review, checks green, Peer Reviewer
   approves, nonauthor merges. No release branch.
3. The integration suite runs on `main` after every merge (or every 15 minutes).
   If it goes red and the I0 merge is in the failing window, the integrator
   reverts it at once (tier A), then the author fixes forward on a new PR.
4. Any I0 revert for a defect is an incident for that agent (section 8).

## 8. Mis-classification and tightening

How it is caught:

- path rules and Peer Reviewer re-scoring before merge;
- a rollback, hotfix or escaped defect whose real impact is above the class used;
- the weekly review (Colony "measure benefit") comparing class with outcome.

What happens (PRINCIPLES.md section 12):

- An under-classified change that reached users is an incident for the author
  in that class of change: its tier drops one step at once.
- Under-scoring caught before merge is not an incident, but is logged. Two in
  30 days for one agent → that agent's changes start one class higher until an
  Owner-merged PR restores it.
- The lesson lands on the layer that owns it (Colony L7): a missed path becomes
  a new path rule, a missed signal becomes a new threshold, a weak test becomes
  a stronger test. A note in a prompt does not count.

## 9. The trail and the cost log

The lane decision lives in the world, not in messages (stigmergy):

- PR labels `impact:I0`…`impact:I3` and `lane:dev|canary|main`;
- a **Lane decision** block in the PR body: six scores, class, path, soak start
  and end, signal readings, promote or rollback, who acted;
- the Flux overlay commit that moved the digest.

Agents read these instead of announcing changes to each other. Steve indexes them.

Each lane step also records its cost in the existing turn-cost ledger
(`tools/turn-cost-ledger`), not in a new register: model, input, cache-read,
cache-write and output tokens, agent and human wall-clock time, priced at
models.dev API rates. The ledger keys rows by PR and lane step, so cost rolls up
by action, turn, work package, workstream and release. The ledger stays private.

## 10. Decision table

| Change | Class | Path | Who promotes to main |
| --- | --- | --- | --- |
| README fix, test-only change | I0 | main (fast path if approved; else next release) | Owner merge |
| Off-by-one fix in one handler | I1 | canary 2 h → main | Owner merge |
| New feature behind a default-off flag | I2 | dev → canary 24 h → main | Owner merge |
| A/B test of a new ranking | I2 | canary only, flag off in prod | experiment ends in canary |
| Additive DB column with backfill | I3 | dev 24 h → canary 72 h → main | Owner merge |
| Rotate an API key, drop a table | I4 | none until the Owner decides | Owner |

### A/B tests in canary

Allowed when production stays isolated: the canary has its own data store (or
read-only access to prod data), the flag is off in prod, traffic ≤ the canary
cap, no external sends, and the experiment has a stop rule, an end date and a
named metric. Results go in the PR. Shipping the winner is a new change, scored
from scratch.

## 11. Changes to existing rules

Each needs the Owner's approval (merge of this file):

1. **I0 fast path to main** without a release PR (section 7). Changes Colony
   item 7 and PRINCIPLES.md section 6 (release PRs are Owner-merged).
2. **Agents deploy to dev and canary overlays** on their own. Today any live
   cluster change is hard limit 3 and Colony item 8 needs separate authority.
3. **Automatic prod rollback** to the previous digest as tier B (section 6).
4. **Higher-class-wins scoring and incident on under-classification** add a new
   incident trigger to PRINCIPLES.md section 12.

Unchanged: Owner merges release PRs; Foreman auto-merges image promotion PRs
after checks and Peer Reviewer; feature PRs merge after Peer Reviewer approves
with checks green; budgets stay capped.

## 12. Open questions for the Owner

1. **I0 straight to main?** Recommended: yes, after a 30-day shadow run where
   agents label I0 and the Owner still merges, with zero I0 reverts for a defect.
2. **Agents deploy to dev and canary without asking?** Recommended: yes, for
   projects at Colony L6 runtime, with automatic rollback attached.
3. **Pre-approve prod rollback to the previous digest?** Recommended: yes, image
   and digest only, never with a data migration.
4. **Can I1 canary → main skip the Owner later?** Recommended: not yet. Revisit
   after 50 I1 promotions with no escaped defect (PRINCIPLES.md section 11).
5. **Soak times and thresholds** (section 4)? Recommended: adopt as written,
   review after the first month of data.
