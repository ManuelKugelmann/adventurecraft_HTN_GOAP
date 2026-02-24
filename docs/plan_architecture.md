# Plan Architecture — Design Notes

Working document capturing design decisions for the HTN-GOAP plan system.
For future refinement and reference.

## Plan Sections

Every plan has exactly two declarative sections:

```
needs { }       — preconditions (boolean, hard filter)
outcomes { }    — postconditions (probabilistic, everything)
```

No `done`, no `estimates`, no `precond`. These two cover everything.

### needs

Hard boolean filters. Must be true or the method is excluded entirely.
Checked against the **agent's belief state**, not world truth.

```acf
plan move_to.walk [movement] {
    needs { $destination.has(Region) AND self.knows(route_to($destination, walking)) }
    ...
}
```

`needs` serves two roles depending on where it appears:
- **On a plan**: requirements the planner must satisfy before execution. If unmet, the planner inserts sub-plans to satisfy them.
- **On a method**: trait/type filter for method selection. Determines which method applies to this situation.

```acf
plan acquire_access [universal] {
    method pick_up {
        needs { $node.has(Physical) AND $node.has(Portable) AND co_located(self, $node) }
        step: do Transfer.Direct { source = $node.location }
    }
    method go_there {
        needs { $node.has(Region) }
        step: do move_to { destination = $node }
    }
    method learn {
        needs { $node.has(Knowledge) }
        step: do acquire_information { about = $node }
    }
}
```

Same keyword, same evaluation, different role based on where it sits.

### outcomes

Probabilistic postconditions. Includes the goal, side effects, and costs.
Time elapsed is just another outcome, not a special field.

```acf
plan attack.ambush [combat] {
    needs { NOT visible(self, $target) AND self.knows(schedule_of($target)) }
    outcomes {
        $target.Vitals.Health -= damage(self, $target), prob = 0.8
        visible(self, $target.allies), prob = 0.4
        self.equipment.weapon.Condition -= 5
        time += distance(self, $ambush_point) / self.Movement.Speed
    }
}
```

The planner chains on outcomes — working backwards from goal, it searches for
plans whose outcomes include the desired state change, checks their needs,
and chains further backwards.

## Hierarchical Composition

Top-level plans are pure composition — just sub-plan references, no concrete
actions. Leaf plans contain actual `do Action.Approach` steps. Methods may
mix sub-plan references and concrete actions.

```
criminal.heist                        ← pure composition
  acquire_information { $target }     ← sub-plan
    acquire_information.bribe         ← mixed (sub-plans + actions)
      influence_person                ← sub-plan
        influence_person.persuade     ← leaf (concrete actions)
    acquire_information.observe       ← leaf
    acquire_information.research      ← leaf
  acquire_access { $tools }           ← sub-plan
  acquire_access { $target_location } ← sub-plan
  move_to { $safehouse }              ← sub-plan
```

Build from both directions:
- **Top down**: decompose high-level goals into sub-plan references
- **Bottom up**: build reusable atomic plans with concrete actions

## Universal Building Blocks

The primitive plan taxonomy everything composes from:

| Plan | Purpose |
|------|---------|
| `acquire_access` | Make a node available to the agent (universal dispatcher) |
| `acquire_item` | Get a physical thing (buy, steal, craft, find, trade) |
| `move_to` | Get self to a location (walk, ride, sail, teleport) |
| `acquire_information` | Learn something (ask, observe, research, explore) |
| `gain_entry` | Get past barriers (unlock, break, sneak, get invited) |
| `influence_person` | Change someone's behavior (persuade, bribe, threaten, deceive) |
| `modify_node` | Change state of an accessible node (craft, repair, destroy) |
| `protect_node` | Prevent modification by others (guard, fortify, hide) |

`acquire_access` is the universal dispatcher — routes to the appropriate
sub-plan based on the node's traits (Physical+Portable → acquire_item,
Region → move_to, Knowledge → acquire_information, etc.).

## Knowledge as Universal Gate

Almost every `needs` check implicitly requires knowledge. The agent doesn't
have perfect information — they plan based on their belief state.

```
ENGINE: reachable(a, b)          ← world truth, used by engine to validate execution
AGENT:  self.knows(X)            ← belief state, used in needs { }
```

Mismatch between what the agent believes and what's true = plan failure at
runtime. This is correct behavior (the bridge was out, the map was wrong).

### Knowledge Types

Facts that gate plan selection:

| Knowledge Type | Gates |
|----------------|-------|
| `route_to(dest, mode)` | All movement plans |
| `location_of(node)` | acquire_access, move_to |
| `properties_of(node)` | Method selection |
| `price_of(item, market)` | Economic plans (buy, sell, trade) |
| `weakness_of(target)` | Efficient attack/influence |
| `schedule_of(person)` | Interception, meeting, ambush |
| `recipe_for(item)` | Crafting (Modify.Structured) |
| `members_of(group)` | Social/political plans |
| `layout_of(location)` | Interior navigation |
| `reputation_of(person)` | Social approach selection |

### Knowledge Acquisition Cascade

Acquiring knowledge is a major fraction of plans. Almost anything chains back
to "but do I know enough to attempt this?":

```
want to do X
  → needs knowledge K to even attempt X
    → acquire_information for K
      → needs access to source of K
        → acquire_access to source
          → needs knowledge of where source is
            → ...bottoms out at explore (always available, worst outcomes)
```

### explore — The Universal Fallback

`acquire_information.explore` is always available. No knowledge needed, but
outcomes are worst-case (high time, high risk, low probability of success).

```acf
plan acquire_information.explore [universal] {
    needs { }
    outcomes {
        self.knows($about), prob = 0.3
        self.knows(nearby(self.location, *)), prob = 0.7
        time += 480
    }
}
```

Method-agnostic — could be walking, sailing, asking strangers, reading signs.
The planner picks based on what the agent has access to.

This is what makes a peasant who's never left their village fundamentally
different from a traveled merchant: not capability, but knowledge. The
merchant's planner skips three layers of information acquisition.

## Drives as Global Needs

Drives are persistent needs checked against accumulated outcomes of every
candidate plan. They don't add new machinery — they're just always-active
constraints.

| Drive | Implicit Global Needs |
|-------|----------------------|
| survival | `alive(self)`, `self.Vitals.Stamina > 0`, `self.Vitals.Hunger < critical` |
| luxury | `self.comfort > threshold` (flexible, deprioritized under stress) |
| dominance | `authority_over(self, subordinates)` maintained |
| belonging | `allied(self, group)` maintained |
| knowledge | (drives acquisition, doesn't constrain) |
| lawful | contracts fulfilled, laws not violated |
| moral | outcomes don't violate `self.moral_code` |

### Drive-Weighted Outcome Evaluation

The planner runs every candidate plan's outcomes against the agent's active
drives. Not just "does this achieve the goal" but "does this violate anything
I care about":

```
plan: steal bread
  outcomes: accessible(self, bread), prob = 0.9
            self.reputation -= 0.1 (if caught, prob = 0.3)

agent with high lawful → rejects, plans buy_bread instead
agent with high survival, low lawful → accepts
agent with high survival, high lawful, starving → accepts (survival overrides)
```

Drive priority shifts with state. Survival dominates when health is low.
Belonging dominates when isolated. The planner weights outcomes by current
drive intensity:

```
outcome_cost = sum(outcome.impact * drive.current_weight)
```

### Automatic Maintenance Plan Insertion

The planner propagates outcomes up the plan tree. When accumulated outcomes
would violate a drive (stamina going negative, health dropping to zero),
that becomes a derived need — the planner auto-inserts maintenance plans:

```
criminal.heist
  acquire_access { $tools }        stamina: 100 → 80
  move_to.walk { $vault }          stamina: 80 → 30
  ← planner inserts rest/potion    stamina: 30 → 70
  breach { $vault_door }           stamina: 70 → 40
  grab { $loot }                   stamina: 40 → 25
  move_to.walk { $safehouse }      stamina: 25 → -10  ← violates survival
  ← planner backtracks, picks move_to.ride instead
```

No special resource management system. Just outcomes flowing up, drive-based
needs being violated, planner inserting fixes. A starving thief doesn't
abandon the heist — the planner inserts "steal some bread on the way."

A contract is the same pattern — a drive with a deadline:

```
fulfil_contract { deliver $goods to $destination before $deadline }
  → lawful/belonging drive generates needs
  → time outcomes accumulate, if total > deadline → plan infeasible
  → reputation outcome if failed
```

## Utility Functions

Cataloged in `schema/utility_functions.acf`. Five categories:

| Category | Purpose | Example |
|----------|---------|---------|
| ENGINE | World-truth, native code | `distance()`, `visible()`, `reachable()` |
| KNOWLEDGE | Agent belief state | `self.knows()` |
| DERIVED | Trait queries + math | `accessible()`, `hostile()`, `alive()` |
| SUGAR | Shorthand for `.has()` | `portable()`, `locked()`, `burning()` |
| PLAN | Sub-plan feasibility | `can_reach()`, `can_acquire()` |

Key distinction: ENGINE functions check world truth (used by the engine to
validate execution). KNOWLEDGE functions check what the agent believes (used
in `needs` for planning). All other functions operate on agent-available data.

## Adversary Response Chains

Adversarial fail points don't have flat costs. When a contested action fails
(actor is detected, lock pick fails, deception is seen through), the adversary
reacts. The cost of failure depends on what the adversary will *choose to do*.

The planner needs to estimate not just P(failure) but E\[cost(failure)\], where
cost depends on the adversary's likely response.

### Two kinds of chain links

**Resolution links** — physical or perceptual contests. Skill vs skill,
resolved by the engine. These are world rules:

- `detection_risk` — can they perceive me? (stealth vs observation)
- `identification_risk` — can they recognize me? (disguise vs familiarity)
- `evidence_risk` — do I leave physical traces? (care vs surface)
- `capture_risk` — can they physically subdue me? (combat/speed)
- `attribution_risk` — can they connect evidence to me? (investigation vs alibi)

**Behavioral links** — the adversary *decides* to act. Not a world rule.
The guard raises the alarm because their role says to. The authority
investigates because their `lawful` drive is violated. The mob attacks
because their `belonging` contract was broken.

The planner estimates behavioral links by consulting its **knowledge** of
the adversary (role, drives, capabilities) and running a shallow plan
simulation: "given this trigger, what would they do?"

### Adversary modeling from knowledge

The planner doesn't have perfect information. It models adversary response
from what it *knows* about the adversary:

1. Read adversary's role (if known): guard → alert/defend/arrest behaviors
2. Estimate which behaviors activate given trigger state
3. For the highest-priority activated behavior, estimate outcome against self
4. **Depth limit**: max 2 levels of inception. "I predict they'll pursue,
   and pursuit resolves via `capture_risk`." NOT "I predict they'll predict
   I'll flee north, so they'll cut me off at the bridge..."

```
self plans heist
  → "if detected, guard will..." (depth 1: read guard role)
    → "guard.alert fires → guard.defend fires" (depth 1: predict behavior)
      → "can they catch me?" (resolution: capture_risk) ← STOP
```

Wrong knowledge = wrong prediction = plan failure at runtime. A thief who
thinks the guards are slow (but they're not) underestimates capture_risk.
This is correct behavior — the system already handles this through the
ESTIMATE/SIMULATE split.

### Evidence is just items

Evidence nodes are ordinary items with Physical trait. No special evidence
system. Footprints are Decayable items created by the `evidence_trace` rule.
Rain (L0 weather rule) decays them. Fire destroys them. An investigator
finds them via `track_following` (skill check on the item). The `cover_tracks`
plan Destroys them.

```
action at location → evidence_trace rule → Create(item with Decayable)
  → weather.rain → Decay rule → item integrity drops → eventually gone
  → cover_tracks → Destroy(item) → gone immediately
  → investigator → track_following (skill check vs item) → knows route
```

No special forensics engine. Just items and the rules that already exist.

### Authorities, laws, and mob justice are contracts

There is no special "legal system." Laws are shared contracts — implicit
agreements within a community. An authority is someone with `authority_over()`.
Law enforcement is a role, not a special system.

When a contract is violated:
- The violated party's `lawful`/`belonging` drives increase urgency
- Their role behaviors activate (guard → arrest, noble → issue warrant)
- Community members with shared contracts respond (mob → confront)
- All of these are just agents planning and acting within the same system

A "warrant" is an Influence.Structured action by an authority, creating a
contract obligation on law_enforcement to pursue the suspect. It's not
special machinery — it's one agent influencing another's priorities.

### Countermeasures attack different links

| Countermeasure | Link type | What it reduces |
|---|---|---|
| Stealth | Resolution | P(detected) — `detection_risk` |
| Disguise | Resolution | P(identified) — `identification_risk` |
| Bribe guard | Behavioral | Guard *chooses* not to alert (Influence step) |
| Speed / diversion | Resolution | P(captured) — `capture_risk` |
| Careful technique | Resolution | P(evidence left) — `evidence_risk` |
| Cover tracks | Resolution | Destroy evidence items (reduces `attribution_risk`) |
| Alibi / flee region | Behavioral | Adversary *chooses* wrong suspect or gives up |

Behavioral countermeasures are plan steps (Influence actions against the
adversary), not probability modifiers. You don't reduce `alarm_risk` — you
execute a plan to bribe the guard, changing their drives/disposition so their
alert behavior doesn't fire.

### Chain composition in outcomes

Plan outcomes express only the resolution links. Behavioral links are
implicit — the planner evaluates them at runtime by consulting its
knowledge of the adversary's role:

```acf
# Resolution links only. Planner fills in behavioral links via role lookup.
visible(self, $guards), prob = detection_risk(self, $guards)
NOT pursued(self), prob = 1 - detection_risk(self, $guards)
                              * capture_risk($guards, self)
NOT attributed(self, theft), prob = 1 - evidence_risk(self, $vault)
                                      * attribution_risk(law_enforcement, self)
```

Between `detection_risk` and `capture_risk` there's an implicit behavioral
link: "will the guard pursue?" The planner reads the guard's role, sees
`defend: when region.threat_level > 70, priority = 50`, and assumes yes.
For a different adversary (distracted merchant, sleeping drunk), the planner
might skip that link entirely.

## Counters: Bidirectional, Cached, Not Ceilings

Counter blocks annotated on plans are **precomputed adversary response
patterns** — cached predictions of what the opposing side will do.
They exist for fast planning, not as hard constraints on behavior.

### Counters form a graph

Plans that oppose each other backreference each other through counters.
Building a secure vault includes checking for known attack patterns.
Planning a heist includes checking for known security patterns. Each
side is authored with awareness of the other:

```acf
plan security.secure_vault [security, economic] {
    method standard {
        reinforce: do Modify.Structured { target = $vault_door }
        guards:    do Influence.Structured { target = $guard_captain }
        alarm:     do Modify.Structured { target = $alarm_system }
    }
    needs { authority_over(self, $vault) }
    outcomes {
        NOT accessible($unauthorized, $vault.contents), prob = 0.9
        time += 48
    }

    # We know what heists look like — counter their observable steps
    counter criminal.heist {
        lockdown  when equipped($subject, lockpicks) AND $subject.pos.near($vault)
        alert     when count(unfamiliar, near($vault)) >= 3 AND time.is_night
        reinforce when $vault_door.condition < 50
    }
}

plan criminal.heist [criminal, economic] {
    method classic {
        intel:  do acquire_information { about = $vault }
        crack:  do gain_entry { target = $vault_door }
        grab:   do acquire_item { source = $vault }
        escape: do move_to { destination = $safehouse }
    }
    needs { self.knows(layout_of($vault)) }
    outcomes {
        accessible(self, $vault.contents), prob = 0.6
        visible(self, $guards), prob = detection_risk(self, $guards)
        time += 120
    }

    # We know what vault security looks like — counter their defenses
    counter security.secure_vault {
        abort     when garrison > crew.weight * 3
        wait      when patrol.active AND patrol.near($entry_point)
        improvise when $vault_door.reinforced AND NOT equipped(self, heavy_tools)
    }
}
```

The heist counters the vault's defenses. The vault counters the heist's
steps. Each plan's counter block references the *opposing plan by ID*
and lists observable conditions that trigger responses. The counter graph
is the adversarial structure of the plan library.

### Bidirectional authoring

When `counters.py` generates counters for a new plan, it works both
directions:

1. **Forward**: What defenses does this plan face? → generate counters
   referencing known defensive plans
2. **Backward**: What existing plans does this new plan threaten? →
   update those plans' counter blocks to recognize the new threat

This means the counter graph stays consistent. Adding `criminal.heist`
also updates `security.secure_vault` to recognize heist patterns.
Adding `security.secure_vault` also updates `criminal.heist` to
recognize new security measures.

### Sequential recognition (not just static pattern match)

Static observables (garrison size, wall height) are easy to check but
easy to circumvent. Real detection recognizes **sequences of actions**
that match a known plan's steps.

Counter conditions can reference accumulated observations:

```acf
counter criminal.heist {
    # Static: obvious conditions
    lockdown when garrison < 3 AND time.is_night

    # Sequential: observed steps matching heist template
    alert    when observed_steps($subject, criminal.heist) >= 2
    pursue   when observed_steps($subject, criminal.heist) >= 3
                  AND visible($subject, $guards)
}
```

`observed_steps(observer, subject, plan_id)` counts how many of the
plan's characteristic actions the observer has *actually perceived*
(gated by `detection_risk` at each step). A thief who scouts the vault
(step 1) and acquires lockpicks (step 2) triggers `alert` even if each
action alone looks innocent. The plan template acts as a detector.

Prematching: the engine clusters plans with similar observable footprints
at load time. `criminal.heist` and `criminal.burglary` share early steps
(scout, acquire tools). An observer who sees those steps gets a partial
match against both — confidence refines as later steps diverge.

### Three tiers of adversary prediction

```
Tier 0: Counter lookup (cheapest)
  "observed_steps >= 2 for heist → counter says alert"
  Pattern match on observables + step count. Retrieve cached response.
  Any agent can do this. O(1).

Tier 1: Role-based prediction (medium)
  "guard detected me → guard role says alert(45) + defend(50) →
   guard WILL pursue → capture_risk resolves whether they catch me"
  Read adversary's role from knowledge. Estimate which behaviors fire.
  Read adversary's counter blocks to see what THEY expect from ME.
  Resolve outcomes against self via resolution functions. Depth 1.

Tier 2: Adversary plan simulation (expensive)
  "their leader owes me a debt and morale is low →
   standard counter says lockdown, but I think I can turn the guard
   with bribery + leverage → novel response not in any counter"
  Model adversary drives, relationships, constraints.
  Read their counter blocks, find gaps or overrides.
  Run shallow adversary planner (depth 2). Requires deep knowledge.
```

A Tier 1 thief reads the vault's counter blocks: "they expect lockpick
approach at night, counter is lockdown. So I'll go during the day with
a forged key instead." The counter backreference lets the agent reason
about *what the adversary expects* — and deliberately subvert it.

A Tier 2 strategist goes further: "their counter expects lockdown, but
the guard captain is underpaid and his family needs medicine. His
drives will override his role if I apply the right pressure."

Simple agents stop at Tier 0. They follow the counter catalog.
Smarter agents read the adversary's counters to find blind spots.
The smartest agents find situations where counters don't apply at all.

### Emergence beyond the catalog

The counter graph is deliberately incomplete. It covers common
adversarial pairs, not every situation. Novel responses emerge when:

- An adversary's drives override their role (starving guard abandons post)
- Relationships create unexpected alliances or betrayals
- Environmental conditions invalidate standard responses (bridge collapsed,
  flood blocks retreat path in counter)
- An agent combines standard plans in a non-standard way
- A counter's preconditions silently fail (garrison undermanned due to festival)

The planner treats counters as the default prediction, then checks
whether the specific adversary's state suggests a different response.

### Inception depth limit

All tiers respect the depth limit:

- **Tier 0**: No depth (lookup, not simulation)
- **Tier 1**: Depth 1 — "I read their role and counters, predict behavior"
- **Tier 2**: Depth 2 — "I predict their plan, including their prediction
  of my most likely approach (from their counter blocks)"

No agent goes to depth 3+. The marginal value of deeper inception drops
fast, and the computational cost rises exponentially. A master strategist
at depth 2 thinks: "they expect me to go at night (their counter), so
I'll go during the day. They might adapt, but I can't predict further."
That's the ceiling. Deeper is infinite regress, not intelligence.

## Open Questions

- How deep should knowledge chaining go before bottoming out at explore?
- Should drives have explicit priority ordering or purely weight-based?
- How does knowledge staleness work? (fact was true when learned, no longer is)
- Should `outcomes` on composite plans be declared or computed from sub-plans?
- How do agents share knowledge? (telling, teaching, written records)
- How should agent intelligence tier (Tier 0/1/2) be determined? Skill-based? Trait?
