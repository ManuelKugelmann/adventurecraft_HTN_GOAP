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
        time += travel_time(self, $ambush_point) + schedule_variance($target)
    }
}
```

The planner chains on outcomes — working backwards from goal, it searches for
plans whose outcomes include the desired state change, checks their needs,
and chains further backwards.

## Hierarchical Composition

Top-level plans are pure composition — just sub-plan references, no concrete
actions. Leaf plans contain actual `do Action.Approach` steps.

```
criminal.heist                        ← pure composition
  acquire_information { $target }     ← sub-plan
    acquire_information.bribe         ← mixed
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
        time += high
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

## Open Questions

- How deep should knowledge chaining go before bottoming out at explore?
- Should drives have explicit priority ordering or purely weight-based?
- How does knowledge staleness work? (fact was true when learned, no longer is)
- Should `outcomes` on composite plans be declared or computed from sub-plans?
- How do agents share knowledge? (telling, teaching, written records)
- Counter-plan generation: how do outcomes inform threat signatures?
