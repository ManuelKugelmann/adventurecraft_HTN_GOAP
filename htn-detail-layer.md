# HTN-GOAP Universal Planner — Detail Layer

## Primitive Actions = AdventureCraft Actions

Every leaf in the HTN tree resolves to exactly one game action call:

```yaml
# The ONLY primitive. Everything decomposes to this.
ActionCall:
  action: Move|Modify|Attack|Defense|Transfer|Influence|Sense
  skill: SkillType             # determines attribute pair
  approach: Direct|Careful|Indirect
  modifiers:
    stealth: 0.0..1.0          # Stealth meta-skill weight
    awareness: 0.0..1.0        # Awareness meta-skill weight
  params:
    target: EntityRef
    objects: ObjectRef[]        # tools, weapons, bribes
    intensity: 0.0..1.0        # high = effective but loud
    secrecy: 0.0..1.0          # high = stealthy but weak
```

### Skill Resolution Table

```
Action    | Direct          | Careful        | Indirect
----------|-----------------|----------------|------------------
Move      | Athletics       | Riding         | Travel
          | Str+Agi         | Agi+Int        | Int+Wil
Modify    | Operate         | Equipment      | Crafting
          | Str+Int         | Agi+Int        | Int+Wil
Attack    | Melee           | Ranged         | Traps
          | Str+Agi         | Agi+Int        | Int+Wil
Defense   | Active Defense  | Armor          | Tactics
          | Agi+Str         | Str+Bod        | Int+Wil
Transfer  | Gathering       | Trade          | Administration
          | Str+Agi         | Cha+Int        | Int+Wil
Influence | Persuasion      | Deception      | Intrigue
          | Cha+Wil         | Cha+Int        | Int+Wil
Sense     | Search          | Observation    | Research
          | Agi+Int         | Int+Wil        | Int+Spi
```

### Trade-off Curves

```
effectiveness = base_skill * intensity * (1 - stealth * 0.5)
detection_risk = intensity * (1 - stealth) * (1 - modifier.stealth)
awareness_bonus = modifier.awareness * (1 - intensity * 0.3)
```

---

## Multi-Timescale Execution

Same ActionCall, different `dt`. The planner doesn't care — resolution scales automatically.

```yaml
TimescaleConfig:
  combat:     { dt: minutes,  precision: leaf,     shell: true  }
  local:      { dt: days,     precision: squad,    shell: maybe }
  regional:   { dt: weeks,    precision: cohort,   shell: false }
  world:      { dt: months,   precision: faction,  shell: false }
  history:    { dt: years,    precision: civ,      shell: false }
```

### How Actions Scale with dt

```yaml
# An individual attacks at dt=minutes
ActionCall:
  action: Attack
  skill: Melee          # Str+Agi
  approach: Direct
  params: { target: enemy_soldier, intensity: 0.8 }
  resolution:
    rolls: 1
    damage: roll(skill_bonus - target.defense)
    duration: 1 action_round

# A cohort (weight=200) attacks at dt=days
# Same ActionCall, but resolved as distribution
ActionCall:
  action: Attack
  skill: Melee
  approach: Direct
  params: { target: enemy_cohort, intensity: 0.8 }
  resolution:
    mode: NormalApprox
    expected_casualties: weight * kill_rate * dt
    variance: weight * kill_rate * (1 - kill_rate) * dt
    duration: dt
```

### Batch Resolution Modes

Inherited directly from world rules — same math for actions:

```
Deterministic:    effect = rate * dt
BernoulliOnce:    p_fire = 1 - (1-p)^dt           # did it happen?
PoissonCount:     n_events ~ Poisson(rate * dt)     # how many times?
NormalApprox:     result ~ N(mean*dt, var*dt)        # CLT for groups
TimeToThreshold:  t ~ InverseGaussian(remaining/rate, remaining²/var)
```

Selection rule:
```
weight == 1  AND dt <= minutes  → single roll
weight == 1  AND dt > minutes   → BernoulliOnce or PoissonCount
weight > 1   AND dt <= days     → PoissonCount (count successes)
weight > 1   AND dt > days      → NormalApprox
any          AND goal-threshold → TimeToThreshold (skip ticks)
```

---

## Probabilistic Planning

Every step in a plan has a computable probability. No magic numbers in the dataset — all derived from actor state.

```yaml
PlanStep:
  type: ActionCall | Expect           # actor does thing | world rule fires
  action: ActionCall?                 # if type == ActionCall
  rule: RuleRef?                      # if type == Expect

  # Probability is ALWAYS an expression over actor/world state
  probability: Expression
  # Examples:
  #   sigmoid(actor.skills.melee + actor.attributes.strength - target.defense - 10)
  #   rule.base_probability * (1 + actor.skills.research * 0.01)
  #   min(1.0, actor.weight / target.weight * actor.skills.tactics / 50)

  on_success: StepRef
  on_failure: StepRef?                # branch or fail plan
  
  # What this step costs (consumed regardless of outcome)
  cost:
    time: Expression                  # ticks at current dt
    resources: Dict[ResourceRef, Expression]
    fatigue: Expression
    detection: Expression             # how much secrecy erodes

  # What this step changes on success
  effects:
    - target: EntityRef
      path: "stat.path"
      op: SET|ADD|REMOVE
      value: Expression
```

### Plan Confidence

```
plan.confidence = product(step.probability for step in critical_path)

# Branching plans:
branch.confidence = branch_entry_probability * product(branch_steps)
plan.confidence = sum(branch.confidence for branch in branches)

# Expected utility (what the planner maximizes):
plan.utility = plan.confidence * goal.value - plan.total_cost
```

### Plan Selection at Different Scales

```
Leaf actor (weight=1):
  → full HTN decomposition to ActionCalls
  → each step rolled individually
  → replan on failure

Squad (weight=5-20):
  → decompose to compound actions
  → fractional allocation: 60% Attack, 20% Defense, 20% Move
  → resolve each fraction as PoissonCount

Faction (weight=1000+):
  → decompose to phases only
  → NormalApprox per phase
  → replan when phase outcome outside 1σ of expected
```

---

## Statistics & Tracking

```yaml
PlanStats:
  plan_template: TemplateRef
  actor_archetype: string            # "cautious_ruler", "aggressive_raider"
  
  executions: int
  successes: int
  failures: int
  
  # Per-step tracking
  step_stats: Dict[StepRef, StepStats]
  
  # Outcome distributions (updated via Bayesian)
  expected_duration: NormalDist       # mean, variance
  expected_cost: NormalDist
  expected_casualties: NormalDist     # for military plans
  
  # Counter effectiveness
  countered_by: Dict[TemplateRef, CounterStats]
  counters_against: Dict[TemplateRef, CounterStats]

StepStats:
  attempts: int
  successes: int
  observed_probability: float        # successes / attempts
  predicted_vs_actual: float         # calibration score
  mean_duration: float
  variance_duration: float

CounterStats:
  encounters: int
  counter_succeeded: int             # counter prevented original plan
  counter_failed: int                # original plan succeeded despite counter
  mean_delay: float                  # how much counter slowed original
```

### Runtime Bayesian Updates

```python
# Actor remembers plan outcomes (stored in knowledge system)
# Prior = dataset probability, updated by experience

prior = plan_template.step[i].probability(actor_state)
likelihood = step_stats.observed_probability
posterior = (likelihood * prior) / evidence

# Actors with more experience have tighter posteriors
# → veterans pick better plans
# → inexperienced actors use dataset defaults
```

### Statistics Aggregation by Timescale

```
dt=minutes:  track individual rolls, exact outcomes
dt=days:     track per-step success counts, aggregate costs
dt=weeks:    track phase outcomes, total plan success/fail
dt=months:   track plan-level stats only
dt=years:    track faction-level win/loss ratios
```

Aging follows the 3-tier history system:
- Recent (≤30 days): full step-level stats
- Medium (30-365 days): plan-level aggregates  
- Ancient (1+ years): template-level success rates only

---

## Counter-Planning with Observables

Counters trigger from **detected ActionCalls**, not plan knowledge.

```yaml
ThreatSignature:
  id: "troops_massing"
  detection_method:                  # what Sense action detects this
    action: Sense
    approach: Careful                # Observation skill
    min_skill: 30
  observables:                       # all grounded in world state
    - "count(entities WHERE faction==threat AND action==Move AND target.distance(self.pos) < 50) > self.garrison * 1.5"
    - "any(entity WHERE faction==threat AND action==Modify AND approach==Indirect AND object.type==siege_equipment)"
  confidence: Expression             # observer's Sense skill affects this
    # sigmoid(observer.skills.sense - threat.modifier.stealth * 50)
  implies_plans:
    - siege: 0.7                     # 70% this means siege
    - raid: 0.2
    - feint: 0.1

CounterEntry:
  threat: ThreatSignature
  counter_plan: TemplateRef
  preconditions:
    - "self.garrison > 50"
    - "self.walls.condition > 30"
  effectiveness: Expression
    # plan.confidence * (1 + self.skills.tactics / 100)
  approach_preference:               # maps to actor drives
    cautious: "Fortify"              # high survival drive
    aggressive: "Sortie"             # high dominance drive
    cunning: "Feint_And_Flank"       # high mental attributes
```

### Counter Depth with Observable Chains

```
Plan A: Siege City
  └─ ActionCalls: Move(army,Direct), Modify(siege_tower,Indirect), Attack(walls,Direct)
     └─ Observable: troops_massing + siege_construction
        │
        ├─ Counter B: Fortify
        │   └─ ActionCalls: Modify(walls,Direct), Defense(garrison,Indirect)
        │      └─ Observable: walls_reinforced + garrison_increased
        │          │
        │          └─ Counter C: Starve_Out (switch from assault to blockade)
        │              └─ ActionCalls: Move(patrols,Careful), Attack(supply_caravans,Indirect)
        │                 └─ Observable: supply_interdiction
        │                     │
        │                     └─ Counter D: Smuggle_Supplies OR Break_Siege
        │
        └─ Counter B2: Call_Allies
            └─ ActionCalls: Influence(ally,Direct), Transfer(payment,Direct)
               └─ Observable: envoy_dispatched (Sense can intercept)
                   │
                   └─ Counter C2: Intercept_Envoy OR Bribe_Ally
```

Every arrow is:
1. A set of ActionCalls that are **observable** (detection_risk > 0)
2. A ThreatSignature that matches those observations
3. A counter-plan selected by `effectiveness * drive_alignment`

Max depth = 4. Beyond that, actors lack information fidelity (knowledge confidence decays per hop).

---

## Fractional Action Allocation (Groups)

Groups don't execute one plan — they split effort across concurrent plans.

```yaml
GroupExecution:
  actor: EntityRef                   # weight > 1
  active_plans: 
    - plan: siege_phase_2
      allocation: 0.60              # 60% of group weight
      action_mix:                    # what ActionCalls this plan needs now
        Attack.Direct: 0.70
        Move.Direct: 0.20
        Modify.Indirect: 0.10
    - plan: maintain_supply
      allocation: 0.25
      action_mix:
        Transfer.Careful: 0.60
        Move.Direct: 0.30
        Defense.Indirect: 0.10
    - plan: scout_perimeter
      allocation: 0.15
      action_mix:
        Sense.Careful: 0.80
        Move.Careful: 0.20

  # Resolution: each fraction resolved independently at current dt
  # Effective weight per action = group.weight * allocation * action_fraction
  # e.g., Attack.Direct weight = 1000 * 0.60 * 0.70 = 420 soldiers attacking
```

### Action Mix Constraints

```
sum(allocation) <= 1.0              # can't exceed total weight
sum(action_mix per plan) == 1.0     # each plan fully allocates its share
max_concurrent_plans <= 4           # performance cap
min_allocation >= 0.05              # below this, not worth tracking
```

---

## Dataset Entry Example

```yaml
# data/verified/military/siege.yaml

task:
  id: "military.siege"
  domain: ["military", "territorial"]
  parameters:
    - target_settlement: EntityRef
    - attacking_force: EntityRef
  methods:
    - id: "assault"
      preconditions:
        - "attacking_force.weight > target_settlement.garrison * 2"
        - "attacking_force.skills.attack > 40"
      priority: "attacking_force.drives.dominance * 0.5 + (1 - attacking_force.drives.survival) * 0.5"
      subtasks:
        - { ref: "military.assemble_force", bind: { destination: "$target_settlement.region" } }
        - { ref: "military.breach_walls", bind: { walls: "$target_settlement.walls" } }
        - { ref: "military.storm", bind: { garrison: "$target_settlement.garrison" } }
    - id: "starve_out"
      preconditions:
        - "attacking_force.weight > target_settlement.garrison * 1.2"
        - "attacking_force.supplies > target_settlement.supplies * 1.5"
      priority: "attacking_force.drives.survival * 0.7"
      subtasks:
        - { ref: "military.assemble_force", bind: { destination: "$target_settlement.region" } }
        - { ref: "military.blockade", bind: { target: "$target_settlement" } }
        - { ref: "common.wait", bind: { condition: "$target_settlement.supplies <= 0" } }
        - { ref: "military.demand_surrender", bind: { target: "$target_settlement.leader" } }

  # Leaf decomposition of breach_walls:
  # → ActionCall(Attack, Traps, Indirect, target=walls, objects=[siege_tower], intensity=0.9, secrecy=0.0)
  # → ActionCall(Attack, Ranged, Careful, target=garrison, objects=[bows], intensity=0.7, secrecy=0.0)
  # → ActionCall(Attack, Melee, Direct, target=gate, objects=[ram], intensity=1.0, secrecy=0.0)

  counters:
    signatures:
      - ref: "threat.troops_massing"
      - ref: "threat.siege_construction"
    responses:
      - { ref: "military.fortify", when: "self.walls.condition > 30" }
      - { ref: "military.sortie", when: "self.garrison > attacking_force.weight * 0.3" }
      - { ref: "political.call_allies", when: "any(edge(self, *, alliance))" }
      - { ref: "military.scorched_earth_retreat", when: "self.garrison < attacking_force.weight * 0.2" }

  sources:
    - { type: "military_doctrine", id: "fm3-90_ch12", confidence: 0.95 }
    - { type: "tvtropes", id: "trope:TheSiege", confidence: 0.7 }
    - { type: "ck3", id: "siege_cb", confidence: 0.8 }

  stats_schema:
    track: [duration, casualties_attacker, casualties_defender, walls_breached_at, surrender_at]
    aggregate_by: [method_chosen, force_ratio, wall_strength]
```

---

## Schema Validation Rules

```
1. Every Task must decompose to ActionCalls within max_depth (6)
2. Every ActionCall uses valid action×approach pair from the 7×3 table
3. Every precondition/effect/probability Expression references only:
   - actor.attributes.{str,agi,bod,wil,int,spi,cha}
   - actor.skills.{23 skills}
   - actor.drives.{7 drives}
   - actor.weight, actor.pos, actor.supplies
   - edge(a, b, type).{debt,reputation,affection,familiarity}
   - target.* (same as actor.*)
   - object.* (item properties)
   - region.* (spatial node properties)
4. Every ThreatSignature.observable references only externally visible state
   (no actor.drives, no actor.plans, no actor.knowledge)
5. Every counter chain terminates within depth 4
6. Every stats_schema.track field maps to a computable Expression
7. sum(group.allocations) <= 1.0
8. No expression references Authority or Reputation directly (they're derived)
```
