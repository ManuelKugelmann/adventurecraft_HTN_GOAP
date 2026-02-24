# Extraction Sources

Catalog of sources for the Universal HTN Tree Dataset, organized by domain.

## Narrative Structure Taxonomies

| Source | Items | Status |
|--------|-------|--------|
| TVTropes | tropes, plot devices, character archetypes, narrative beats | queued |
| Aarne-Thompson-Uther (ATU) | ~2500 folktale types | queued |
| Christopher Booker's Seven Basic Plots | 7 plot decompositions | queued |
| Joseph Campbell's Monomyth | Hero's Journey stages | queued |
| Propp's 31 Narrative Functions | 31 morphological functions | partial |
| Ronald Tobias' 20 Master Plots | 20 plot structures | queued |
| Georges Polti's 36 Dramatic Situations | 36 dramatic templates | queued |
| Blake Snyder's Save the Cat | beat sheet categories | queued |
| Dramatica Theory | story points | queued |

## Game AI / Design References

| Source | Items | Status |
|--------|-------|--------|
| Dwarf Fortress wiki | emergent behavior catalogs, job trees, need hierarchies | queued |
| RimWorld AI task trees | ThinkerNodes, JobGivers | queued |
| STRIPS/GOAP operators (F.E.A.R.) | Jeff Orkin's published action sets | queued |
| Utility AI catalogs (Dave Mark) | GDC behavior presentations | queued |
| CK3/EU4 wiki | AI decision trees for diplomacy, war, economy | queued |
| The Sims | need/interaction catalogs | queued |
| Civilization | tech/decision trees | queued |
| OpenAI Gym / PettingZoo | environment action spaces | queued |

## Behavioral / Social Science

| Source | Items | Status |
|--------|-------|--------|
| Maslow's Hierarchy | need decomposition | queued |
| BDI Agent Literature | belief-desire-intention models | queued |
| Erving Goffman | interaction rituals, face-work | queued |
| Game Theory | canonical scenarios (prisoner's dilemma, ultimatum, coordination) | queued |
| Organizational Behavior | delegation, authority chains, conflict resolution | queued |
| Sun Tzu / Clausewitz | strategy decompositions | queued |

## Domain-Specific Action Catalogs

| Source | Items | Status |
|--------|-------|--------|
| Medieval Guilds | occupation/guild task lists (historical) | partial |
| Military Doctrine (FM 3-0) | tactical task frameworks | partial |
| D&D/Pathfinder SRD | action economy, spell/ability taxonomies | queued |
| GURPS | action catalogs | queued |
| Wikipedia "list of" pages | occupations, crimes, trade goods | queued |
| Wikidata | structured knowledge graphs | queued |

## LLM Processing Pipeline

For each source:
1. Decompose into `CompoundTask -> Method[] -> PrimitiveTask[]` triples
2. Tag with: domain, preconditions (grounded in actor/world state), effects, typical actors, frequency
3. Cross-reference duplicates across sources to build confidence scores
4. Validate output against .acf schema
5. Generate counter-plans for plans
