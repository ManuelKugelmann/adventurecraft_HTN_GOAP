# AdventureCraft — Architecture

## 1. Core

One node type. Traits are everything. Same rules at every scale.

---

## 2. Units

```
Space:  1 tile = 33cm
Time:   1 tick = 10 seconds (compound action: maneuver, probe, commit)
dt:     int32 tick count, never fractional
Clock:  int64 world tick counter
```

---

## 3. Fixed-Point

```
Fixed — Q16.16, int32, 0x00010000 = 1.0
    Range: ±32767, Precision: 1/65536
```

All simulation state. `ToFloat()` one-way gate for rendering only.
mul/div via int64 intermediate. Transcendentals: lookup tables (sigmoid, sqrt, Ziggurat normal).
IDs, tick counters, quantities: plain integers.

---

## 4. Node

```
Node {
    Id: NodeId                  // 32-bit monotonic
    Template: TemplateId
    Weight: int32               // count (1=individual, >1=batch/group)
    ContainerNode: NodeId       // physical: where I am (null if top-level)
    ParentNode: NodeId          // hierarchy: group/org parent (null if root)
    Flags: byte
}   // ~20 bytes, fully blittable
```

Two trees, reverse-mapped via external indices:

```
ContainerIndex: NativeParallelMultiHashMap<NodeId, NodeId>   // what's inside me
HierarchyIndex: NativeParallelMultiHashMap<NodeId, NodeId>   // my group members
```

Updated when ContainerNode or ParentNode changes.

### Everything Is a Node

| Node | Weight | Key Traits |
|------|--------|-----------|
| Person | 1 | Vitals, Attributes, Skills, Drives, Agency |
| Horse | 1 | Vitals, Attributes |
| Garrison | 200 | Vitals, Attributes, Skills, Drives |
| Grain pile | 500 | Edible, Perishable, Condition |
| Sword | 1 | Weapon, Condition |
| Arrow bundle | 50 | Weapon |
| Ship | 1 | Spatial, Vehicle, Vitals, Condition |
| Trade fleet | 10 | Spatial, Vehicle, Vitals |
| Tile | 1 | Spatial, Climate |
| Planet | 1 | Spatial, Climate, NaturalResource |
| Faction | 10000 | Vitals, Attributes, Skills, Drives |
| Knowledge | 1 | Immaterial, Mirrors, StatCopy, Obscurity |
| Contract | 1 | Immaterial, ContractTerms |
| Authority claim | 1 | Immaterial, AuthStrength, AuthScope |
| Tavern kitchen | 1 | Spatial |
| Corpse | 1 | Condition |
| Ghost | 1 | Vitals, Attributes, Drives |
| Food | 1 | Edible, Perishable, Condition |

### Containment (physical tree)

```
sword.ContainerNode = alice
alice.ContainerNode = ship_cabin
ship_cabin.ContainerNode = ship
ship.ContainerNode = ocean_tile
```

A node is "a place" if it has SpatialTrait. Any node can contain other nodes.
Held items: ContainerNode = holder. Position derived by walking chain.

### Hierarchy (organizational tree)

```
soldier.ParentNode = squad           Weight=1
squad.ParentNode = company           Weight=49
company.ParentNode = regiment        Weight=500
```

Split: variance exceeds threshold → create child nodes, distribute stats, adjust Weight.
Merge: children similar → collapse back, bump parent Weight.
Promote: split off Weight=1 child for story relevance. Remains child of group.

### Ownership

Legal claim, separate from containment. OwnedBy relationship trait.
Alice owns sword even after dropping it.

---

## 5. Traits

Each trait kind is its own blittable struct with named fields.
Every trait has `Owner: NodeId`. Relationship traits also have `Target: NodeId`.
Fixed size per type, variable across types.

### Cardinality

**Single:** max one per node. `NativeHashMap<NodeId, int>` (O(1) exact).
**Multi:** many per node. `NativeParallelMultiHashMap<NodeId, int>`.

### Entity Stat Traits (all Single)

```
VitalsTrait {                   // HOT — every tick
    Owner: NodeId
    Health: Fixed
    Hunger: Fixed
    Thirst: Fixed
    Fatigue: Fixed
    Mood: Fixed
    Wounds: Fixed
    Mana: Fixed
}

AttributesTrait {               // WARM — action resolution
    Owner: NodeId
    Str: Fixed
    Agi: Fixed
    Bod: Fixed
    Will: Fixed
    Wit: Fixed
    Spi: Fixed
    Cha: Fixed
}

SkillsTrait {                   // WARM — action resolution
    Owner: NodeId
    Skills[23]: Fixed           // 0-20: 7×3, 21: stealth, 22: awareness
}

DrivesTrait {                   // COLD — L4 planner only
    Owner: NodeId
    Survival: Fixed
    Luxury: Fixed
    Dominance: Fixed
    Belonging: Fixed
    Knowledge: Fixed
    Lawful: Fixed
    Moral: Fixed
}

AgencyTrait {                   // COLD — only entities with plans
    Owner: NodeId
    ActivePlan: TemplateId
    ActivePlanStep: int
}
```

| Trait | Frequency | Writers | Readers |
|-------|----------|---------|---------|
| Vitals | Every tick | L1, L3 | L1, L3, L4 |
| Attributes | Rare | L4 training | Action resolution |
| Skills | Rare | L4 training | Action resolution |
| Drives | Near-never | Story events | L4 planner |
| Agency | Per plan step | L4 planner | L4 executor |

Authority (Social Power), Reputation (Social Endurance): derived from Social traits. Never stored.

### Object Property Traits (all Single)

```
WeaponTrait         { Owner, Damage: Fixed, Speed: Fixed, Range: Fixed }
ArmorTrait          { Owner, Protection: Fixed, Encumbrance: Fixed }
PerishableTrait     { Owner, Rate: Fixed }
FlammableTrait      { Owner, Ignition: Fixed, FuelValue: Fixed }
EdibleTrait         { Owner, Nutrition: Fixed, Taste: Fixed }
ToolTrait           { Owner, Domain: int, Bonus: Fixed }
ContainerTrait      { Owner, Capacity: Fixed }
HeavyTrait          { Owner, Mass: Fixed }
FragileTrait        { Owner, BreakThreshold: Fixed }
ValuableTrait       { Owner, BasePrice: Fixed }
StackableTrait      { Owner, Max: int }
MaterialTrait       { Owner, MaterialType: int }
LightSourceTrait    { Owner, Brightness: Fixed, FuelRate: Fixed }
ConcealedTrait      { Owner, Bonus: Fixed }
ConditionTrait      { Owner, Condition: Fixed, Quality: Fixed }
ImmaterialTrait     { Owner }
```

### Spatial Traits (all Single)

```
SpatialTrait        { Owner, ScaleLevel: int, Capacity: Fixed }
ClimateTrait        { Owner, Temperature: Fixed, Humidity: Fixed }
HydrologyTrait      { Owner, Water: Fixed }
LightingTrait       { Owner, Light: Fixed }
BurningTrait        { Owner, Fire: Fixed, Fuel: Fixed }
SoilTrait           { Owner, Fertility: Fixed }
PopulatedTrait      { Owner, Population: int, ThreatLevel: Fixed }
VehicleTrait        { Owner, Speed: Fixed }
```

A node with SpatialTrait is "a place" others can be inside.

### Relationship Traits (all Multi, keyed by Target)

```
Social              { Owner, Target, Debt: Fixed, Rep: Fixed, Aff: Fixed, Fam: Fixed }
MemberOf            { Owner, Target, Rank: Fixed, Since: int }
DelegatesTo         { Owner, Target, Scope: int, Grants: int }
KnowsAbout          { Owner, Target, Confidence: Fixed, Freshness: Fixed }
Guards              { Owner, Target, Priority: Fixed }
HostileTo           { Owner, Target, Intensity: Fixed }
AlliedWith          { Owner, Target, Strength: Fixed }
EmployedBy          { Owner, Target, ContractId: NodeId }
ConnectedTo         { Owner, Target, Throughput: Fixed, TerrainCost: Fixed, Width: Fixed, Conductivity: Fixed }
OwnedBy             { Owner, Target }
Adjacent            { Owner, Target }
ActiveRole          { Owner, Target: TemplateId }
Mirrors             { Owner, Target }
AuthScope           { Owner, Target }
DelegatedFrom       { Owner, Target }
```

| Relationship | Constraint |
|---|---|
| OwnedBy | n:1 (one owner per item) |
| Mirrors | n:1 (one real entity per v-item) |
| All others | n:m |

### Multi Property Traits (Multi, keyed by discriminator)

```
NaturalResource     { Owner, Kind: int, Amount: Fixed }          // keyed by Kind
StatCopy            { Owner, FieldPath: int, Value: Fixed }      // keyed by FieldPath
```

### Virtual Item Traits (Single, on nodes with ImmaterialTrait)

```
ObscurityTrait      { Owner, Value: Fixed }
PlanMetaTrait       { Owner, CurrentStep: int, TotalSteps: int, Confidence: Fixed }
ContractTermsTrait  { Owner, ContractType: int, Status: int, Duration: int, Frequency: int }
AuthStrengthTrait   { Owner, Force: Fixed, Consensus: Fixed, Tradition: Fixed, Delegation: Fixed }
```

---

## 6. Trait Storage

### Single Traits

```
SingleTraitTable<T> where T : unmanaged {
    Data:     NativeList<T>
    ByOwner:  NativeHashMap<NodeId, int>                // Owner → index (1:1)
}
```

### Multi Traits

```
MultiTraitTable<T> where T : unmanaged {
    Data:     NativeList<T>
    ByOwner:  NativeParallelMultiHashMap<NodeId, int>   // Owner → indices (1:n)
    ByTarget: NativeParallelMultiHashMap<NodeId, int>   // Target → indices (reverse)
}
```

### Operations

| Operation | Single | Multi |
|-----------|--------|-------|
| All of kind | `for i in Data` | `for i in Data` |
| Node X's | `ByOwner[X]` → exact | `ByOwner.GetValuesForKey(X)` |
| Who targets X? | — | `ByTarget.GetValuesForKey(X)` |
| Add | Append + insert | Append + insert |
| Remove | Swap-remove + update | Swap-remove + update |
| Update field | `Data[idx].Field = val` | `Data[idx].Field = val` |

No sorting. Swap-remove keeps Data dense. All Burst-compatible.

### Uniform Field Access (for interpreter and GPU)

All trait payload fields are Fixed. Layout registered at startup:

```
TraitLayout {
    KindId: ushort
    HasTarget: bool
    FieldCount: int
    PayloadOffset: int              // bytes before first Fixed field
    FieldNames: string[]
    IsSingle: bool
}
```

Typed structs for C#/codegen. Raw `byte* + offset` for interpreter and GPU. Same data.

---

## 7. Skills

```
Idx  Action     Approach     Name              Attr1+Attr2
0    Move       Direct       Athletics         Str+Agi
1    Move       Indirect     Riding            Agi+Wit
2    Move       Structured   Travel            Wit+Will
3    Modify     Direct       Operate           Str+Wit
4    Modify     Indirect     Equipment         Agi+Wit
5    Modify     Structured   Crafting          Wit+Will
6    Attack     Direct       Melee             Str+Agi
7    Attack     Indirect     Ranged            Agi+Wit
8    Attack     Structured   Traps             Wit+Will
9    Defense    Direct       Active Defense    Agi+Str
10   Defense    Indirect     Armor             Str+Bod
11   Defense    Structured   Tactics           Wit+Will
12   Transfer   Direct       Gathering         Str+Agi
13   Transfer   Indirect     Trade             Cha+Wit
14   Transfer   Structured   Administration    Wit+Will
15   Influence  Direct       Persuasion        Cha+Will
16   Influence  Indirect     Deception         Cha+Wit
17   Influence  Structured   Intrigue          Wit+Will
18   Sense      Direct       Search            Agi+Wit
19   Sense      Indirect     Observation       Wit+Will
20   Sense      Structured   Research          Wit+Spi
21   —          —            Stealth           (modifier)
22   —          —            Awareness         (modifier)
```

Skill bonus = skill + attr1 + attr2. Attr pairs data-driven.

---

## 8. Rules

### Authoring (.acf)

```
rule hunger_drain:
    layer: L1_Biology
    scope: Vitals
    effect: Accumulate Vitals.Hunger rate=-0.001

rule starvation:
    layer: L1_Biology
    scope: Vitals
    condition: Vitals.Hunger > 90
    effect: Accumulate Vitals.Health rate=-0.01

rule sword_decay:
    layer: L2_Items
    scope: Condition
    effect: Decay Condition.Condition rate=0.0001 floor=0

rule eat_food:
    layer: L3_Basic
    scope: Vitals
    condition: Vitals.Hunger > 50
    condition: contains(Owner, Edible)
    effect: Transfer Edible.Nutrition into=Vitals.Hunger

rule melee_combat:
    layer: L4_Complex
    scope: HostileTo
    condition: distance(Owner, Target) < Weapon.Range
    effect: SkillCheck Attack.Melee vs Defense.ActiveDefense
    effect: Accumulate Vitals.Health value=-Weapon.Damage mitigated=Armor.Protection

rule heat_spread:
    layer: L0_Physics
    scope: ConnectedTo
    effect: Spread Climate.Temperature conductivity=ConnectedTo.Conductivity
```

### Generic Representation (IR)

Parser expands .acf to generic ops. Two consumers: codegen and interpreter.

```
struct RuleCondition {
    ushort TraitKind;
    byte Field;
    Compare Op;                 // GT, LT, GTE, LTE, EQ, NEQ, Exists, NotExists
    ValueSource Value;
}

struct RuleEffect {
    EffectOp Op;                // Accumulate, Decay, Set, Transfer, SkillCheck,
                                // Spread, Create, Destroy, AddTrait, RemoveTrait
    EffectTarget Target;        // Owner, Target, Both
    ushort TraitKind;
    byte Field;
    ValueSource Value;
    ValueSource Mitigator;      // optional
    Fixed Probability;          // 1.0 = deterministic
}

struct ValueSource {
    SourceKind Kind;            // Literal, TraitField, NodeField, Function
    Fixed Literal;
    ushort TraitKind;
    byte Field;
    BuiltinFn Function;         // distance, contains, sigmoid, count, depth (if Kind=Function)
}

enum Compare    : byte { GT, LT, GTE, LTE, EQ, NEQ, Exists, NotExists }
enum EffectOp   : byte { Accumulate, Decay, Set, Transfer, SkillCheck,
                          Spread, Create, Destroy, AddTrait, RemoveTrait }
enum SourceKind : byte { Literal, TraitField, NodeField, Function }
enum BuiltinFn  : byte { Distance, Contains, Sigmoid, Count, Depth }
```

All conditions AND. OR = separate rule.

### Elementary Ops

```
Accumulate      field += rate * dt  (or field += value - mitigator)
Decay           field moves toward floor/ceiling at rate * dt
Set             field = value
Transfer        move value from source field to target field
SkillCheck      sigmoid(attacker_skill - defender_skill) → probability gate
Spread          propagate value along connections by conductivity
Create          spawn node from template
Destroy         remove node
AddTrait        attach trait to node
RemoveTrait     detach trait from node
```

### Built-in Functions (conditions and value sources)

```
distance(A, B)          container chain walk → tile distance
contains(node, kind)    ContainerIndex → any contained node with trait?
count(node, kind)       ContainerIndex → how many contained with trait
sigmoid(x)              lookup table, probability mapping
depth(node)             container chain length
```

Both codegen and interpreter implement these. List grows with the game.

### Rule Struct

```
WorldRule {
    Id: int
    Layer: byte                     // L0..L4
    Scope: ushort                   // TraitKind to iterate
    MinScale: byte
    MaxScale: byte
    Probability: Fixed
    Conditions: RuleCondition[]
    Effects: RuleEffect[]

    // Auto-derived at registration:
    BatchModes: BatchMode[]
    MaxDt: int
    ThresholdPairs: ThresholdPair[]
}
```

### Batch Modes (auto-derived from effect + probability)

| Effect | Deterministic | Stochastic |
|--------|--------------|------------|
| Accumulate | Linear | NormalApprox |
| Decay | Linear | NormalApprox |
| Set | Immediate | Bernoulli |
| Transfer | Linear | NormalApprox |
| Create | (invalid) | Poisson |
| Destroy | Immediate | Bernoulli |
| AddTrait | Immediate | Bernoulli |
| RemoveTrait | Immediate | Bernoulli |

---

## 9. Execution

### Two Tiers

```
Tier 1: Code-generated Burst/HLSL from .acf at build time
        All shipping rules. SkillCheck, Spread, distance, contains
        are codegen targets, not special cases.

Tier 2: Generic interpreter over RuleCondition/RuleEffect
        Mods, prototyping, runtime hot-reload.
        Walks IR at runtime. Correct, slower.
```

Promote workflow: prototype in Tier 2 → verify → build → Tier 1 takes over. No rule rewrite.

### Tick

```
Tick(world, dt: int32):
    apply PlayerCommands (sorted by player id)
    for layer in L0..L4:
        for rule in layer:
            if partition.scale outside [rule.MinScale, rule.MaxScale]: skip
            READ  (parallel): evaluate conditions, compute deltas. Pure.
            WRITE: resolve deltas, apply, clear.
```

### Delta

```
struct Delta {
    NodeId Owner;
    int Key;                    // 0 for single. Target/discriminator for multi.
    ushort TraitKind;
    byte Field;
    DeltaOp Op;                 // Add, Set
    Fixed Value;
    int Priority;
    int RuleId;
}
```

Add: commutative sum. Set: highest priority, RuleId tiebreak. Deterministic.

### Determinism

- Fixed or int everywhere. No floats in sim.
- PRNG: `hash(world_seed, tick, rule_id, subject_id)` per roll.
- Read-write separation per layer. All reads see pre-layer snapshot.
- Mutations via delta buffer only.

### Parallelism

Read phase: Burst IJobParallelFor over trait Data arrays.
Write phase: single-threaded.
Layers: sequential L0→L4.
Spatial partitions: parallel within layer, sync at boundary.

### Burst Field Access

Traits stored as structs. Jobs access specific fields via unsafe pointer + offset.
Zero-copy. Burst supports this natively.

```
[BurstCompile]
struct AccumulateJob : IJobParallelFor {
    [NativeDisableUnsafePtrRestriction] byte* traitData;
    int stride;                 // sizeof(T)
    int fieldOffset;            // byte offset of target field
    Fixed rate;
    int dt;

    void Execute(int i) {
        Fixed* field = (Fixed*)(traitData + i * stride + fieldOffset);
        *field += rate * Fixed.FromInt(dt);
    }
}
```

---

## 10. Scale

```
enum SpatialScale : byte {
    Tile, Room, Building, Block, District, Settlement,
    Region, Province, Continent, Planet, System, Sector, Empire
}
```

Tile grid: Tile through Settlement (cells, physics, LOS).
Graph: Settlement and above (topology, aggregate stats).
Coordinates local to containing node. Stellar = travel-time edges.

| Scale | dt | Layers |
|-------|-----|--------|
| Active (player) | 1–6 ticks (10s–1min) | L0–L4 |
| Settlement (off-screen) | 8,640 (1 day) | L0–L4 batched |
| Region | 60,480 (1 week) | L1–L4 |
| Province | 259,200 (1 month) | L2–L4 |
| Continent+ | 3,153,600+ (1 year+) | L3–L4 |

Tier transitions: one catch-up tick at dt=gap.
Worldgen: same sim at dt=1 year for N centuries.

---

## 11. Multiplayer & Distribution

### Authoritative Server

Clients send PlayerCommands, receive filtered deltas.
Single-player = local server + one client. No code path difference.
Fog of war: knowledge system filters per player per trait kind.

### Distributed Servers

Each server owns a spatial partition.
Cross-partition: boundary messages (entity transfer, remote deltas).
Delta merge: Add=sum (commutative), Set=priority+RuleId (deterministic).
Sync barrier per layer before write phase.

---

## 12. Virtual Items

Nodes with ImmaterialTrait. No separate type.
Get forgery, staleness, theft, propagation for free.

| V-Item Kind | Traits |
|---|---|
| Knowledge | Immaterial + Mirrors + StatCopy(s) + Obscurity |
| Plan | Immaterial + PlanMeta |
| Contract | Immaterial + ContractTerms + party relationships |
| Order | Immaterial + authority relationship |
| Authority claim | Immaterial + AuthStrength + AuthScope |

Plan steps in templates. Runtime tracks current step index only.
Meta-knowledge: v-item Mirrors another v-item. Recursive.

---

## 13. Templates

```
NodeTemplate {
    Id: TemplateId
    Parent: TemplateId?             // template inheritance
    DefaultWeight: int
    DefaultTraits: TraitInstance[]   // stamped onto node on CREATE
}
```

CREATE = allocate node, walk template parent chain, copy default traits.

---

## 14. Node Deletion

DESTROY(node) queues cascade in write phase:

```
1. Remove all traits owned by this node (ByOwner scan per table)
2. Remove all relationship traits targeting this node (ByTarget scan per multi table)
3. Reparent contained nodes to this node's ContainerNode
4. Reparent children to this node's ParentNode
5. Update ContainerIndex and HierarchyIndex
6. Swap-remove node from NativeList
```

---

## 15. Open Points

### 15.1 Effect Owner vs Target

Relationship-scoped rules (PerTrait(HostileTo)) need effects that target the Owner,
the Target, or both. RuleEffect has `EffectTarget: Owner | Target | Both`.

But resolving "Target's VitalsTrait" requires a cross-node lookup:
iterate HostileTo → get Target NodeId → lookup Vitals.ByOwner[Target] → get index → apply delta.

The codegen handles this. The delta targets the Target's node, not the iterated trait's owner.
**Resolved architecturally. Codegen emits the right lookup chain.**

### 15.2 SkillCheck as EffectOp

SkillCheck appears in the EffectOp enum but it's really a condition modifier (gates subsequent
effects with a probability derived from skill differential). It's not a mutation.

**Options:**
- A) SkillCheck is a special Condition, not an Effect. Condition evaluates sigmoid(skill_diff),
     sets probability for subsequent effects.
- B) SkillCheck is an Effect that modifies the rule's effective probability mid-evaluation.

**Recommendation:** A. SkillCheck is a condition type.

```
struct RuleCondition {
    ...
    // When Op = SkillCheck:
    //   TraitKind/Field = attacker skill index
    //   Value = ValueSource pointing to defender skill
    //   Evaluates sigmoid(attacker - defender) as probability gate
}
```

This means SkillCheck is removed from EffectOp. Effects are pure mutations.
Conditions are pure reads (including probabilistic gates).

Revised EffectOp:
```
enum EffectOp : byte { Accumulate, Decay, Set, Transfer, Spread,
                        Create, Destroy, AddTrait, RemoveTrait }
```

Revised Compare:
```
enum Compare : byte { GT, LT, GTE, LTE, EQ, NEQ, Exists, NotExists, SkillCheck }
```

### 15.3 Spread Semantics

Spread propagates a value along ConnectedTo edges. But the iteration scope is ConnectedTo
(a relationship trait). The effect reads Owner's Climate.Temperature, reads Target's
Climate.Temperature, computes delta based on difference × conductivity, and writes to both.

This is a dual-target effect (modifies both Owner and Target spatial nodes).
EffectTarget=Both handles this, but both sides need their own delta (one positive, one negative,
equal magnitude → conservation).

**Resolved:** codegen emits two deltas per Spread evaluation. Conservation enforced by symmetry.

### 15.4 Interpreter Performance for Mods

Tier 2 interpreter walks IR at runtime. With millions of traits, even simple rules
could be slow. Mod rules might apply to hot trait tables (Vitals, Climate).

**Mitigation:** mod rules can declare a max scope (e.g. only nodes with a specific template
or within a spatial region). Scope narrowing reduces iteration count.
Not a phase 1 problem. Monitor and optimize when modding ships.

### 15.5 Template .acf Format

Not yet defined. Needs:
- Rule syntax (sketched above)
- Template definition syntax (node defaults + trait instances)
- Template inheritance syntax
- File loading, validation, hot-reload

**Phase 1:** C# data structures. .acf parser is phase 2.

### 15.6 Modding: Runtime Trait Registration

Phase 1: hardcoded trait tables in World struct.
Phase 2: `Dictionary<ushort, ITraitTable>` for mod-registered kinds.
TraitLayout enables interpreter + GPU access for mod traits.

---

## 16. Summary

```
1 node type:        Node (~20 bytes, blittable)
2 trees:            ContainerNode (physical) + ParentNode (hierarchy)
2 indices:          ContainerIndex, HierarchyIndex (NativeParallelMultiHashMap)
N trait types:       blittable structs in SingleTraitTable or MultiTraitTable
Trait access:        typed structs for C#, raw byte+offset for interpreter/GPU
Rules:               named in .acf → parsed to IR (Condition[] + Effect[])
Elementary ops:      Accumulate, Decay, Set, Transfer, Spread,
                     Create, Destroy, AddTrait, RemoveTrait
Built-in functions:  distance, contains, count, sigmoid, depth
Conditions:          field comparisons + SkillCheck (probabilistic gate)
Execution:           2 tiers: codegen Burst/HLSL (shipping) + interpreter (mods)
Batch modes:         auto-derived (Linear, Bernoulli, Poisson, NormalApprox)
Delta:               { Owner, Key, TraitKind, Field, Op, Value, Priority, RuleId }
Math:                Fixed Q16.16 everywhere
Time:                1 tick = 10s, dt = int32, clock = int64
Determinism:         seeded PRNG, delta buffer, no shared mutable state
Parallelism:         Burst IJobParallelFor over trait arrays
Distribution:        spatial partitions, delta merge across servers
Scale:               33cm tile to stellar empire, adaptive dt, same rules
Templates:           TemplateId → parent chain + default traits
Virtual items:       nodes with ImmaterialTrait
```
