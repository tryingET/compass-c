```json
{
  "claim_checks": [
    {
      "claim": "The frame was frozen at the stated hash and timestamp before any probe ran.",
      "verdict": "unverifiable",
      "evidence": "insufficient_evidence: repo/docs/decisions/2026-09-26-rethink-frame.md asserts transcript evidence, but the underlying timestamped transcript and hash computation are not supplied."
    },
    {
      "claim": "The retained natural-use candidates contain five Pi invocations, each consisting only of one SKILL.md read, with no user COMPASS mention.",
      "verdict": "verified",
      "evidence": "probe2/probe2-data.json contains five natural_invocation rows with skill_md:1, no other detected calls, and user_mentions:0. This verifies the exported classification, not successful reads or search completeness."
    },
    {
      "claim": "There were zero natural notebooks among 195 notebooks under HOME.",
      "verdict": "unverifiable",
      "evidence": "insufficient_evidence: probe2/probe2-data.json supplies aggregate counts only. No notebook inventory, discovery procedure, database inspection output, or deletion receipts establish exhaustive coverage."
    },
    {
      "claim": "Zero of five triggering final answers contained reversal or reconsideration language.",
      "verdict": "unverifiable",
      "evidence": "insufficient_evidence: probe2/probe2-data.json mentions the scan but supplies neither final answers nor its exact regex/results; probe2/classify.py does not implement that scan."
    },
    {
      "claim": "The three COMPASS-C tasks have 34 evidence records: 26 pass, five fail and three skip.",
      "verdict": "verified",
      "evidence": "The 34 ak/evidence-*.json exports have that distribution and task IDs 5424, 5641 or 5673. Failures are 9094, 9168, 9198, 9267 and 9362; skips are 9028, 9169 and 9234."
    },
    {
      "claim": "Thirteen commit subjects match the frozen P1 pattern.",
      "verdict": "verified",
      "evidence": "git/log.txt matches repo/docs/decisions/2026-09-26-rethink-frame.md's regex for the thirteen listed commits. This verifies selection, not every causal catcher attribution."
    },
    {
      "claim": "cb3c54b corrected guidance requiring redundant get reads after mutations.",
      "verdict": "verified",
      "evidence": "git/cb3c54b.txt replaces the blanket readback instruction with inspection of validated lifecycle replies. repo/evals/dogfood/v4-lifecycle/README.md records the preceding redundant-read effort failure."
    },
    {
      "claim": "33d2c90 corrected a scope snapshot from entity_version 5 to 7 after a gate failure.",
      "verdict": "verified",
      "evidence": "git/33d2c90.txt contains exactly that change; ak/evidence-9173.json records CI rejection of version 5 versus live version 7."
    },
    {
      "claim": "README and the GLM study README omit the later grading-invalidity caveat while retaining historical improvement counts.",
      "verdict": "verified",
      "evidence": "repo/README.md retains 20/24 versus 19/24; repo/evals/observations/2026-09-11-glm-native/README.md retains two improvements and one regression. Both include limitations, but neither states ak/evidence-9198.json's finding that both improvements depend on inconsistent grading."
    },
    {
      "claim": "release.json still says host_installation:not_performed despite subsequent local installations.",
      "verdict": "verified",
      "evidence": "repo/release.json contains that value. ak/evidence-9174.json and ak/evidence-9182.json document local Codex and Pi installation; ak/evidence-9183.json documents the additional skill link. These do not establish ChatGPT account installation."
    },
    {
      "claim": "The retained build record still recommends accepting bounded v0.5.0, while later lifecycle outcomes lack dependency links.",
      "verdict": "verified",
      "evidence": "repo/evals/dogfood/v4-lifecycle/continuing-build-record.json contains that non-stale recommendation and two later lifecycle outcome notes with empty depends_on arrays. It also preserves an earlier successful invalidation; the whole record is not uniformly stale."
    },
    {
      "claim": "The dated publication receipt is a historical snapshot rather than a stale current-head claim.",
      "verdict": "verified",
      "evidence": "repo/docs/project/verified-publication.json explicitly scopes itself to the public-main snapshot at verified_at and permits later branch advancement."
    },
    {
      "claim": "The existing posture gate forced eleven posture commits in eight days.",
      "verdict": "unverifiable",
      "evidence": "git/file-change-dates.tsv lists eleven posture-changing commits, including initialization. repo/scripts/check-document-policy.sh establishes a mandatory validation workflow, but insufficient_evidence establishes that all eleven commits were caused by it or measures their incremental cost."
    },
    {
      "claim": "M2's table totals are fifteen catches out of twenty-one, approximately 71%.",
      "verdict": "verified",
      "evidence": "Counting the marks in repo/docs/decisions/2026-09-26-rethink-probe-report.md gives six P1 catches and nine P2 catches when partial item 4 receives full credit. This verifies arithmetic only, not guard behavior."
    },
    {
      "claim": "The pilot-attempt continuation is necessarily a currently stale instruction rather than preserved historical evidence.",
      "verdict": "unverifiable",
      "evidence": "repo/evals/dspx-jury/pilot-attempt.json retains the old budget-protocol instruction, but repo/evals/dspx-jury/README.md labels that pilot historical and describes its superseding subscription continuation. ak/evidence-9311.json explicitly preserves the failed attempt as immutable. insufficient_evidence establishes which artifact currently governs continuation."
    }
  ],
  "overclaims": [
    "R1 is satisfied by the author's hypothetical labels, not by an observed mechanism. Reporting support for C without carrying that distinction into the decision risks promoting assumed detectability into demonstrated prevention. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; repo/docs/decisions/2026-09-26-rethink-probe-report.md.",
    "Zero detected downstream tools is not zero downstream effect. The answer scan is unavailable and would not establish causal benefit or its absence anyway. Sources: probe2/probe2-data.json; probe2/classify.py.",
    "Calling persistence's zero uptake evidence of rejection overlooks the product's explicit transient default and permission requirement. Sources: repo/skills/compass/SKILL.md; repo/docs/project/vision.md.",
    "R3 cannot establish an intrinsic notebook unit-of-record mismatch from this sample. The notebook can link evidence and other note kinds; the frame restricts M1-ideal to decision-shaped items while giving M2 hypothetical document-wide coverage. Neither automatically identifies the correct dependency. Sources: repo/src/compass_c/core.py; repo/docs/decisions/2026-09-26-rethink-frame.md.",
    "A's natural-pull condition is met under the frozen R4 definition; its guidance condition is untested. A is not established, but treating the result as rejection of its trajectory overstates the test. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; repo/docs/decisions/2026-09-26-rethink-probe-report.md.",
    "A stale linked historical artifact does not automatically make its referring claim false. README's self-dogfood link genuinely documents dogfood, although it may inadequately represent ongoing use. Sources: repo/README.md; repo/evals/dogfood/2026-09-08/final-brief.json; repo/evals/dogfood/v4-lifecycle/continuing-build-record.json."
  ],
  "gaps": [
    "The same author selected P2 after seeing the defects and knowing a B+C prior. Freezing afterward prevents subsequent edits, not selection bias. P1 selects corrected survivors by wording and overrepresents policy-driven posture updates. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; git/log.txt.",
    "Twenty-one items are not twenty-one independent incidents: multiple GLM documents share AK9198 as their superseding evidence, and several P1 rows update the same posture file. There is no representative denominator of decisions, unchanged claims, or evidence changes. Sources: repo/docs/decisions/2026-09-26-rethink-probe-report.md; ak/evidence-9198.json; git/file-change-dates.tsv.",
    "M2 has no prospectively declared dependency manifests or execution receipts. In particular, merely referencing an unchanged old final-brief path cannot reveal newer work elsewhere without additional predeclared dependencies. Sources: repo/README.md; repo/docs/decisions/2026-09-26-rethink-frame.md.",
    "Precision, severity and avoided harm are missing. A broad evidence-path or task-level alert may fire correctly but add no useful correction beyond M0. Counting partial P2 item 4 as a miss leaves 14/21, still above 60%; three total downgrades from the published score would leave 12/21, below it. Twice a zero comparator contributes no meaningful discrimination. Sources: repo/docs/decisions/2026-09-26-rethink-probe-report.md.",
    "Natural-use search recall and specificity are unvalidated. classify.py matches strings in arbitrary tool arguments, not successful reads or executions; it misses relative compass.py calls, the supported compass executable alias, and direct library use. The first-pass search and session identifiers are absent. Sources: probe2/classify.py; probe2/probe2-data.json; repo/pyproject.toml.",
    "Session counts are not exposure-adjusted opportunities. Pi installation is documented on September 11, after the search window begins; equivalent Claude exposure is unestablished. Five candidate sessions span only four project names. Sources: ak/evidence-9182.json; probe2/probe2-data.json.",
    "Routing judgments conflate reading with primary ownership. The lehrplan request includes a real API-versus-CLI choice as well as an explicitly named specialist. Without complete turns, classifying that read as inappropriate ownership is insufficient_evidence. Existing overlap tests concern ownership, not every incidental read. Sources: probe2/probe2-data.json; repo/skills/compass/SKILL.md; repo/skills/compass/evals/cases.json.",
    "The replay omits demonstrated active-use benefits by construction, including earlier notebook invalidation, and mixes historical snapshots, original errors and changed-evidence drift. That is acceptable for a bounded diagnostic, not a complete product-value ranking. Sources: repo/evals/dogfood/v4-lifecycle/continuing-build-record.json; repo/docs/decisions/2026-09-26-rethink-probe-report.md."
  ],
  "missed_second_order": [
    "Hypothesis: broad guards induce agents to refresh dates, narrow dependencies or relabel living documents as snapshots to restore green CI. Operators may then trust compliance instead of substance. Existing freshness machinery makes this adaptation plausible, but it is unmeasured. Sources: repo/scripts/check-document-policy.sh; repo/docs/decisions/2026-09-26-rethink-frame.md.",
    "Hypothesis: task-level AK triggers create alert fan-out; validation evidence can itself trigger further revalidation. Operator attention, not annotation count, becomes the scarce resource. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; ak/evidence-9173.json.",
    "Hypothesis: adding AK-dependent enforcement shifts cost and availability constraints into the owner's workflow and competes with existing task authority. A guard cannot itself authorize resolving an out-of-scope contradiction. Sources: repo/docs/project/vision.md; repo/AGENTS.md; ak/task-5673.json.",
    "Hypothesis: host discovery, tool-catalog exposure and native memory can dominate observed adoption. The GLM study already observed unnecessary persistence and used a custom Pi/MCP integration; routing and persistence are not solely product preferences. Sources: repo/evals/observations/2026-09-11-glm-native/README.md; ak/evidence-9182.json.",
    "Hypothesis: stronger models commoditize generic guidance while making dependency capture cheaper. That can simultaneously weaken the skill's differentiation and strengthen durable, exact, cross-session notebook workflows; the direction is not uniformly against A or for B. Sources: repo/docs/project/vision.md; repo/evals/dogfood/v4-lifecycle/README.md.",
    "Hypothesis: freezing prevents another self-generated evaluation/maintenance cycle and preserves attention, but silent abandonment can leave installed users relying on obsolete claims. Freezing and withdrawing existing installations are distinct decisions. Sources: repo/docs/project/product_posture.md; ak/evidence-9174.json; ak/evidence-9182.json."
  ],
  "steelman_A": "The strongest case is not that a notebook should police every README. Consequential, revisitable decisions need portable state, model lineage, atomic evidence revision and cold handoff even when they occur infrequently. The retained lifecycle exercise demonstrates those capabilities, and the earlier build record demonstrates actual dependency invalidation. Neither proves general benefit, but both are better evidence of A's intended function than document-drift recall. Guidance-only use and opt-in persistence are intentional; zero notebooks in mostly transient work may be appropriate behavior. Better agents could reduce capture friction without eliminating the need for durable external state. Sources: repo/docs/project/vision.md; repo/skills/compass/SKILL.md; repo/evals/dogfood/v4-lifecycle/README.md; repo/evals/dogfood/v4-lifecycle/run-3/root-readback-check.json; repo/evals/dogfood/v4-lifecycle/continuing-build-record.json.",
  "steelman_E": "Five model-initiated reads do not demonstrate operator-valued outcomes or justify continuing expenditure. The quality study has invalid grading, later adjudication has its own semantic failure, and ordinary uptake is not established beyond routing. The prospective guard is generic infrastructure, not a reason to maintain COMPASS-C as a growing product. Preserving v0.6.0 and the negative findings retains option value while stopping discretionary development. This is an opportunity-cost argument, not a claim that the frozen E rule is satisfied: maintenance exceeding benefit remains unmeasured. Sources: probe2/probe2-data.json; ak/evidence-9198.json; ak/evidence-9362.json; repo/docs/decisions/2026-09-26-rethink-frame.md; repo/docs/decisions/2026-09-26-rethink-probe-report.md.",
  "conclusion_changes": {
    "R1": "Retain 'formally met under the frozen hypothetical scoring'; replace any empirical endorsement with 'C remains an unvalidated candidate.' The arithmetic survives removing partial credit, but dependency adoption, prospective detection and net benefit are insufficient_evidence. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; repo/docs/decisions/2026-09-26-rethink-probe-report.md.",
    "B_not_evidenced": "Retain, narrowly. No demonstrated natural kernel demand is supplied; that does not prove unwantedness. The frozen B condition includes 'wanted', which invocation counting does not test, and installed canaries establish capability rather than spontaneous demand. Sources: repo/docs/decisions/2026-09-26-rethink-frame.md; probe2/probe2-data.json; ak/evidence-9174.json.",
    "routing_fix": "Downgrade from an identified fix to an untested causal hypothesis. The current description already excludes complexity-only and specialist-owned tasks. Host behavior, mixed requests and read-versus-ownership confusion remain alternative explanations. Existing negative cases alone cannot establish improved precision without lost recall on unseen positive cases. Sources: repo/skills/compass/SKILL.md; repo/skills/compass/evals/cases.json; probe2/probe2-data.json."
  },
  "most_informative_next_observation": "One independently observed, naturally occurring consequential evidence-change episode, with dependencies fixed before the change, comparing an actually operating guard against the existing AK workflow and opt-in notebook: which first produces an actionable correction, whether the owner changes the decision, and the full attention cost including irrelevant alerts. A successful prospective episode would be mechanism evidence, not a population-rate estimate. This directly addresses the largest missing bridge in repo/docs/decisions/2026-09-26-rethink-probe-report.md: hypothetical catch to useful correction.",
  "recommendation": {
    "choice": "E*: a reversible freeze of discretionary product expansion, preserving v0.6.0 and explicit opt-in use. Do not select C from this replay or treat a routing change as proven. This is a recommendation, not an executed archive or a finding that all frozen E conditions hold. Basis: repo/docs/decisions/2026-09-26-rethink-probe-report.md; ak/evidence-9198.json; repo/evals/dogfood/v4-lifecycle/README.md.",
    "reversal_conditions": [
      "Reconsider A if independently observed, owner-chosen consequential decisions repeatedly use cold resume or revision and show benefits exceeding full capture/review costs against the existing workflow. Relevant capability baseline: repo/evals/dogfood/v4-lifecycle/README.md.",
      "Reconsider C if prospective independent observation demonstrates timely, materially useful corrections beyond M0, with predeclared dependencies and owner-accepted false-alert and maintenance costs. Relevant unresolved premise: repo/docs/decisions/2026-09-26-rethink-frame.md.",
      "Reconsider B if external consumers repeatedly request or independently use calculations/invalidation without wanting the broader workflow. Relevant untested demand condition: repo/docs/decisions/2026-09-26-rethink-frame.md.",
      "Reconsider D only when real owner forecasts have frequent, verifiable resolutions and sustained review demand; these probes do not establish that population. Source: repo/docs/decisions/2026-09-26-rethink-frame.md."
    ],
    "confidence": "medium"
  }
}
```

## Assessment

**The report establishes documentary drift more convincingly than it establishes a product direction.** Several concrete defects survive inspection: the missing grading-validity caveat, outdated installation status, and unrevised build recommendation. Those are genuine findings, not evidence that the proposed guard would have prevented them at acceptable cost. Sources: `repo/README.md`, `repo/release.json`, `ak/evidence-9198.json`, and `repo/evals/dogfood/v4-lifecycle/continuing-build-record.json`.

The central comparison is asymmetric. M1-used receives the consequences of actual adoption failures; M2 receives successful hypothetical dependency declarations. Yet declaring the right dependencies is precisely the difficult behavior both approaches require. M2 automates detection **after that work**, not discovery of every relevant relationship. Its advantage must survive prospective declaration, irrelevant changes, missed sources and actual operator response. Sources: `repo/docs/decisions/2026-09-26-rethink-frame.md` and `repo/scripts/check-document-policy.sh`.

Selection compounds this asymmetry. P2 was chosen with the preferred mechanism and defects already known. P1 rewards mechanisms that produced recognizable correction commits. Multiple rows reflect shared underlying events, so “21 items” exaggerates the number of independent opportunities. The report acknowledges these limitations but still lets the pooled percentage carry substantial directional weight. Sources: `repo/docs/decisions/2026-09-26-rethink-frame.md`, `git/log.txt`, and `ak/evidence-9198.json`.

The strongest overlooked counterexample is the notebook’s demonstrated use, not its idealized score. Its retained record actually invalidated dependent reasoning, and the lifecycle exercise retained state through a cold handoff. These observations do not establish market demand or superiority, but they prevent a clean inference from “poor README-drift coverage” to “wrong product abstraction.” Sources: `repo/evals/dogfood/v4-lifecycle/continuing-build-record.json` and `repo/evals/dogfood/v4-lifecycle/run-3/root-readback-check.json`.

Conversely, routing is weak evidence against freezing. An agent reading a skill is not an operator choosing to maintain it. Nor does narrowing already restrictive wording necessarily improve outcomes: it could suppress useful incidental comparisons while leaving host-selection behavior unchanged. Sources: `probe2/probe2-data.json` and `repo/skills/compass/SKILL.md`.

**My decision would be a reversible freeze, not a declared architectural victory.** Preserve the demonstrated capabilities and their limitations; require independently observed usefulness before renewed expansion. Confidence is medium because the evidence supports restraint more strongly than it supports permanent abandonment. Sources: `repo/docs/project/product_posture.md` and `repo/docs/decisions/2026-09-26-rethink-probe-report.md`.