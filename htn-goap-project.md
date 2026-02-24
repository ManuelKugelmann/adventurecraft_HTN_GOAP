# HTN-GOAP Universal Planner

## Schema

```yaml
# === CORE TYPES ===

Action:                          # Primitive — maps to game action
  id: string                     # "attack_melee", "trade_offer"
  game_action: ActionType        # Move|Modify|Attack|Defense|Transfer|Influence|Sense
  skill: SkillType               # mapped skill
  approach: Direct|Careful|Indirect
  preconditions:                 # all grounded in world state
    - expr: "target.hp > 0"
    - expr: "actor.pos.distance(target.pos) < weapon.range"
  effects:
    - expr: "target.hp -= damage"
    - expr: "actor.reputation[target.faction] -= 5"
  cost: Expression               # evaluated at planning time
  duration: Expression            # ticks

Method:                          # One way to accomplish a Task
  id: string
  preconditions: Expression[]    # when is this method applicable
  subtasks: TaskRef[]            # ordered sequence
  priority: Expression           # method selection ranking

Task:                            # Compound — decomposes into Methods
  id: string
  domain: string[]               # ["combat", "social", "economic", ...]
  parameters: Param[]
  methods: Method[]              # ordered by priority
  
Plan:                            # Instantiated task tree
  id: string
  root_task: TaskRef
  actor: ActorRef
  status: Pending|Active|Blocked|Failed|Complete
  current_step: int
  context: Dict                  # bound variables
  counter_to: PlanRef?           # if this is a counter-plan
  observable_signature: string[] # what other actors can detect

# === COUNTER-PLANNING ===

ThreatSignature:                 # Observable pattern that triggers counters
  id: string
  observables: Expression[]      # "actor.troops_near(target) > threshold"
                                 # "actor.recent_actions contains 'scout'"
  confidence: float              # how certain the detection is
  implies_tasks: TaskRef[]       # what plans this likely indicates

CounterEntry:                    # Links threats to responses
  threat: ThreatSignature
  counter_task: TaskRef          # the counter-plan template
  preconditions: Expression[]    # can we actually execute this counter
  effectiveness: Expression      # estimated success vs this threat
  
# === KNOWLEDGE INTEGRATION ===

TaskSource:                      # Provenance tracking
  source_type: string            # "tvtropes"|"atu"|"propp"|"military"|...
  source_id: string              # "trope:XanatosGambit"
  confidence: float              # LLM extraction confidence
  human_verified: bool

TaskTemplate:                    # Pre-decomposed from sources
  task: Task
  sources: TaskSource[]
  tags: string[]                 # ["betrayal", "siege", "trade_war"]
  complexity: int                # nesting depth
  typical_actors: string[]       # ["ruler", "merchant", "spy"]
  narrative_beat: string?        # "rising_action"|"climax"|"resolution"
```

## Counter-Plan Depth

```
Plan A (attacker): Siege City
  └─ observable: troops_massing, supply_lines_established
     │
     ├─ Counter B (defender): Fortify + Sortie
     │   └─ observable: walls_reinforced, cavalry_assembled
     │       │
     │       ├─ Counter C1: Feint + Flank (adapts siege)
     │       └─ Counter C2: Starve Out (switch strategy)
     │
     └─ Counter B2 (ally): Relief Army
         └─ observable: allied_army_approaching
             │
             └─ Counter C3: Ambush Relief Column
```

Detection is always grounded:
- `actor.pos`, `actor.visible_actions[]`, `actor.resource_levels`
- `relationship[a,b].reputation`, `knowledge[observer].confidence`
- Never "knows enemy plan" — only "observes indicators"

## Repo Structure

```
htn-universal-planner/
├── README.md
├── LICENSE                      # MIT
├── schema/
│   ├── task.schema.json         # JSON Schema for validation
│   ├── action.schema.json
│   ├── counter.schema.json
│   └── threat.schema.json
├── data/
│   ├── raw/                     # LLM-extracted, unverified
│   │   ├── tvtropes/
│   │   ├── atu_folktales/
│   │   ├── propp/
│   │   ├── polti/
│   │   ├── military/
│   │   ├── rimworld/
│   │   ├── ck3/
│   │   └── dnd_srd/
│   ├── verified/                # human-reviewed
│   │   ├── combat/
│   │   ├── social/
│   │   ├── economic/
│   │   ├── political/
│   │   └── survival/
│   └── counters/                # threat-counter mappings
│       ├── military.yaml
│       ├── political.yaml
│       ├── economic.yaml
│       └── social.yaml
├── scripts/
│   ├── ingest/
│   │   ├── llm_extract.py       # LLM → structured YAML pipeline
│   │   ├── scrape_tvtropes.py
│   │   ├── parse_atu.py
│   │   ├── parse_propp.py
│   │   ├── decompile_rimworld.py
│   │   └── merge_duplicates.py  # cross-source dedup
│   ├── validate/
│   │   ├── schema_check.py      # JSON Schema validation
│   │   ├── precondition_lint.py # ensure all refs are grounded
│   │   └── cycle_detect.py      # no circular task deps
│   ├── analyze/
│   │   ├── coverage_report.py   # what domains/actions are covered
│   │   ├── depth_stats.py       # decomposition depth distribution
│   │   └── counter_gaps.py      # threats with no counters
│   └── export/
│       ├── to_csharp.py         # emit C# structs
│       ├── to_dot.py            # Graphviz export
│       └── to_mermaid.py        # Mermaid diagrams
├── viz/
│   ├── index.html               # interactive tree browser
│   ├── plan_simulator.html      # step-through plan execution
│   └── counter_graph.html       # threat/counter network
├── tests/
│   ├── test_schema.py
│   ├── test_decomposition.py    # every Task must fully decompose to Actions
│   ├── test_preconditions.py    # all preconditions reference valid state
│   ├── test_effects.py          # effects modify valid state
│   ├── test_counters.py         # counter chains terminate
│   └── scenarios/               # integration tests
│       ├── siege_and_counter.yaml
│       ├── trade_war.yaml
│       ├── assassination_plot.yaml
│       └── rebellion.yaml
├── prompts/
│   ├── extract_task.md          # LLM prompt: source → Task YAML
│   ├── extract_counter.md       # LLM prompt: Task → ThreatSignature + Counter
│   ├── verify_grounding.md      # LLM prompt: check preconditions grounded
│   └── narrative_tag.md         # LLM prompt: tag narrative beats
└── .github/
    └── workflows/
        ├── validate.yml         # CI: schema + lint on PR
        └── coverage.yml         # CI: coverage report
```

## Roadmap

### Phase 1 — Foundation
- [ ] Repo init, schema definitions, CI
- [ ] `llm_extract.py` — core pipeline: source text → structured YAML
- [ ] `schema_check.py` + `precondition_lint.py`
- [ ] Extract 50 tasks from Propp (simplest, most structured source)
- [ ] Extract 50 tasks from military doctrine
- [ ] Basic Mermaid visualization

### Phase 2 — Scale
- [ ] TVTropes scraper + extraction (batch via Claude API)
- [ ] ATU folktale extraction
- [ ] RimWorld/CK3 decompilation → task trees
- [ ] `merge_duplicates.py` — cross-source dedup with similarity scoring
- [ ] Coverage report: actions × domains matrix

### Phase 3 — Counters
- [ ] ThreatSignature extraction from existing tasks
- [ ] Counter-plan generation (LLM: "given this plan, what observable? what counter?")
- [ ] Counter-chain depth testing (max 3-4 levels)
- [ ] `counter_gaps.py` — find uncountered threats

### Phase 4 — Viz & Testing
- [ ] Interactive HTML tree browser (D3 or React)
- [ ] Plan simulator: pick actor + goal → watch decomposition
- [ ] Counter graph: network visualization of plan/counter relationships
- [ ] Scenario tests: full plan execution with mock world state

### Phase 5 — Integration
- [ ] C# export matching AdventureCraft DSL
- [ ] Runtime HTN planner using dataset
- [ ] GOAP fallback for unmatched goals
- [ ] Counter-plan triggering from knowledge system observations

## LLM Extraction Pipeline

```
Source Text ──→ [extract_task.md prompt] ──→ Raw YAML
                                              │
                ┌─────────────────────────────┘
                ▼
         schema_check.py ──fail──→ retry with error context
                │ pass
                ▼
         precondition_lint.py ──fail──→ retry: "ground this in actor state"
                │ pass
                ▼
         merge_duplicates.py ──→ deduplicated verified/ YAML
                │
                ▼
         [extract_counter.md] ──→ ThreatSignature + CounterEntry
```

Key prompt design:
- Always include the Expression grammar so LLM outputs valid preconditions
- Always include 2-3 gold examples per source type
- Request confidence scores — reject < 0.7

## Visualization Ideas

**Tree Browser**: collapsible task trees, color by domain, click to see full YAML, search/filter by tag. Show which sources contributed to each node.

**Plan Simulator**: select an actor archetype + goal → animate HTN decomposition step by step. Show precondition checks (green/red). Show method selection. Allow "what if" state overrides.

**Counter Graph**: force-directed graph where nodes are plans, edges are "counters" relationships. Cluster by domain. Click a node to see the full counter chain. Highlight gaps (uncountered plans).

**Coverage Heatmap**: 7 actions × N domains matrix. Cell color = number of tasks covering that combination. Instantly see blind spots.

## Testing Tool

```python
# Scenario definition
scenario:
  world_state:
    actor_a: { hp: 100, pos: [10,10], faction: "red", troops: 500 }
    actor_b: { hp: 100, pos: [20,20], faction: "blue", troops: 300 }
    city: { pos: [20,20], walls: 50, garrison: 200, owner: "blue" }
  
  plans:
    - actor: actor_a
      goal: "control(city)"
      # HTN planner picks: Siege City → [March, Encircle, Bombard, Assault]
  
  expected:
    - actor_b detects threat via: "enemy.troops_near(city) > garrison * 1.5"
    - actor_b counter-plan: Fortify + Request_Aid
    - plan_a method switches when: "city.walls > 80"  # fortification detected
  
  assertions:
    - "city.owner == 'red' OR actor_a.plan.status == 'Failed'"
    - "len(actor_b.executed_counters) >= 1"
    - "no_ungrounded_preconditions()"
```

Run via: `python -m pytest tests/scenarios/ -v`

## Additional Ideas

**Narrative Arc Tagging**: every task gets a `narrative_beat` — setup/rising/climax/falling/resolution. Enables the game to prefer plans that create good story pacing.

**Plan Personality**: different actor archetypes prefer different methods for the same task. A cautious leader picks "Negotiate" over "Attack". Map to the 9-attribute system: high-Mental actors prefer Indirect approaches.

**Plan Memory**: actors remember which plans succeeded/failed against specific opponents. Shift method priorities based on history. Stored in knowledge system.

**Emergent Alliances**: when two actors detect the same threat, generate a "Joint Counter" task that requires coordination. Observable: both actors sending envoys.

**Betrayal Detection**: certain plan signatures (troop repositioning, secret meetings) can be cross-referenced to indicate betrayal. Counter: preemptive strike or diplomatic confrontation.

**Economic Warfare**: trade embargo, price manipulation, counterfeiting. These map to Transfer/Influence actions but have very different counter signatures than military plans.

**Modding API**: expose task/counter YAML as moddable content. Modders add new plans without touching code. Schema validation ensures mod plans are well-formed.
