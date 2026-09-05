# Make Borders Great Again

Victoria 3 hands over territory one state at a time. This mod hands it over one **province**
at a time: pick a country, pick one of its states, and click the provinces you want on the
map.

It is two things in one folder, and they are kept apart on purpose:

- **A mechanism.** Everything needed to name a province, put it in front of a player, work
  out whether it can be taken, and move it. It knows nothing about when taking a province is
  allowed, and it names no part of the map.
- **An implementation.** A diplomatic action, a debug panel, a war goal and the game rules
  that gate them. This is one way to use the mechanism, not the only one.

If you want the second, enable the mod and set the game rule. If you want the first, see
[Using it from your own mod](#using-it-from-your-own-mod).

Requires the [Community Mod
Framework](https://github.com/Victoria-3-Modding-Co-op/Community-Mod-Framework).

---

## Load it last

**Put MBGA below every other mod in the playset.**

MBGA overwrites no file of the base game and no file of any other mod. That is not enough on
its own. A mod may claim a whole folder in its `replace_paths`, and the game then reads that
folder from it alone, ignoring what every mod loaded **before** it put there — file names and
prefixes do not enter into it. Total conversions claim folders MBGA needs, `common/decisions`
and `common/country_definitions` among them.

Loaded after such a mod, MBGA's own files are read and everything works. Loaded before it,
they are dropped: the probe countries are gone, so nothing can be demanded, and the game
reports `create_country effect [ Invalid tag ]`.

Nothing about this can be fixed from inside the files, by us or by anyone. It is decided by
the order alone, so put MBGA at the bottom.

---

## What the engine will not do

Most of this mod is shaped by what Victoria 3 refuses to answer. None of the following is a
matter of finding the right syntax; they were each tried and each came back with an error, an
empty result, or the wrong scope.

| Wanted | What the engine says |
| --- | --- |
| The provinces of a state | There is no province iterator on a state. `every_province` demands a *province* scope, and the only iterator that yields provinces at all is `every_province_in_<geographic region>`. |
| A province by number, or a province's neighbours | Neither exists. A province can be reached only through `p:xRRGGBB` written out in full, or from a battle. |
| Whether two provinces touch | Nothing asks it. The nearest thing is a question about their *states*. |
| A variable on a province | Provinces do not support variables. State regions do. |
| A province's position | Not readable in script, and not readable in the interface either. |
| Which province is a state's city, port, farm, mine or wood hub | Declared in the map data, never readable back. |
| Moving a province | `set_owner_of_provinces` takes literal ids only. Nothing moves a province held in a scope. |
| A map mode that computes something | `map_painting_mode` is an engine enum. There is no hook. |

The mod works around every one of these. How it does it is the rest of this document.

---

## How it works

### The province index

The map is walked once at the start of a game and every province is filed under its own state
region in a variable list. That is the whole solution to "the provinces of a state": ask the
state's region for its list and keep the ones that are in the state you asked about.

The walk goes through **geographic regions**, because `every_province_in_<short_key>` is the
only thing in the game that hands out province scopes, and it exists only for regions declared
in script. The key is part of the effect name and is fixed when the game loads, so it cannot
be built from anything the mod learns while running.

So the mod tries keys, widest first, and stops as soon as it is done:

1. a generated index, if a module for this map is loaded — exact, and costs no walking;
2. `old_world` and `new_world`, which between them are the base game's whole land map, and
   that of anything keeping its region names — Anbennar included;
3. every other key that could ever be needed, from
   `common/scripted_effects/mbga_known_worlds.txt`, tried one at a time. That list holds the
   base game's names and those of installed mods that both redraw the map *and* put land
   somewhere `old_world` and `new_world` do not reach — a mod that plays on the base game's
   map contributes nothing, however many regions it declares for its own events.

It knows when to stop because the engine can be asked how large the map is: `every_state_region`
names nothing and `num_provinces` is the engine's own count for one of them, so summing them
gives every province on the map. A walk that reached only part of it cannot pass for a whole
one, and the mod says so in the log rather than quietly listing less than there is.

Each attempt is an effect of its own, since one naming a region this map does not declare is
thrown out whole and would take the others with it.

The index lives on **state regions** rather than states because a state is one owner's share
of a region and comes and goes as borders move, while a region is fixed for the life of the
map.

### Containers

A province cannot be put in front of a player. A data model item cannot be promoted to a
province, and the interface has no province type to bind to. A **script container** can: it
is a scope the interface can hold, and it can carry variables.

So every candidate province gets a container that wraps it. The interface renders containers,
hands the clicked one back, and script unwraps the province inside. Everything a row needs to
draw itself is a variable on the container.

### Which provinces border yours

To take a province you must be able to reach it. Since the engine will not say whether two
provinces touch, the mod makes each one the entire territory of a throwaway country and asks
whether that country's state borders another. That works on any map, and it costs two
province transfers per province — which is what makes a large state slow.

So the answer is worked out ahead of time instead, from `map_data/provinces.png`, where two
provinces are neighbours when their colours meet along a pixel edge, and from
`map_data/adjacencies.csv`, which carries the straits and canals joining provinces that meet
nowhere on the map at all. That is the **lookup table**: 230 000 entries covering the base
game's map.

The table is *checked, not trusted*. When a state opens, the mod fills the neighbours from the
table and counts how many containers ended up with any. A table made for this map fills them;
one made for a different map names provinces that are elsewhere or nowhere and fills nothing.
Failing that check, everything found is thrown away and the engine is asked the slow way.

**With a table, opening a state costs no province transfers at all.** Whether a province
touches your land becomes a question about who owns its neighbours, which is free.

### What it remembers

Without a table the mod asks the engine, and it only ever asks once. A container is built for
a province the first time its state is opened and then kept for the rest of the save, carrying
what it has learned: which province it is, which hub, and which provinces it touches. Which
province touches which is a fact about the map and does not expire, so a state region gives up
its shape once however many times it is opened, in however many wars.

Two things are remembered apart. That every pair inside a region has been settled means the
sweep never runs there again. That the neighbour lists reach past the region's own edge — which
only a table can say, since probing finds neighbours only among the provinces on offer — means
no province need be lent out to ask whether it borders you.

So on a map with no table the first opening of a region is the expensive one, and every
opening after it is cheaper; on a map with one, none of them costs anything.

### The courier

`set_owner_of_provinces` only takes ids written out in full, which is no use when the province
is a scope. So the province is given to a throwaway country of its own, and the receiver
annexes that country immediately. Three such countries exist — two for asking about borders,
one for carrying — and none is ever seen: they are raised and removed inside one effect chain.

This is where the mod costs the player something, because the engine has no notion of handing
over a province: an annexation is what it gives you, so a transfer costs what an annexation
costs. Building levels come through it intact; their workforce and any Company Headquarters do
not. See the [FAQ](#what-does-taking-a-province-cost-the-state-it-came-from).

### Staying connected

Provinces are taken one at a time, and each one has to touch either your own land or something
you have already taken in this session. Handing a province back can cut another one off from
your border; when that happens the stranded province is handed back too.

---

## Game rules

| Rule | Settings | What it does |
| --- | --- | --- |
| **Province Demands** | Bordering only *(default)* / Anywhere in the state | Whether a province has to touch land you hold. |
| **Province Transfer Tool** | Off *(default)* / Diplomatic action / Debug panel | How the tool is reached. Off means provinces change hands through war only. |
| **Province Scanning** | Short waits / Balanced *(default)* / Fewest interruptions | How much work a state may cost when it opens. **Does nothing on any map the mod has a table for**, which includes the base game's. It is there for a mod that redraws the map and ships no table of its own. |

The first two are read in `common/scripted_guis` and nowhere deeper. The mechanism itself
never asks what the game permits.

---

## Building a table for a redrawn map

If your mod changes the map, MBGA still works — it falls back to asking the engine, which is
correct everywhere and slow on large states. A table makes it free.

```
python tools/make_compat.py "C:/path/to/your mod"
```

That is the whole job. It reads your mod's map the way the game does — `provinces.png`,
`province_terrains.txt`, `map_data/state_regions`, and `replace_paths` if you use it — and
writes a finished compatibility mod next to your folder: metadata, dependencies, adjacency
table, hub table, nothing left to fill in.

The output carries the **same file names** as MBGA's own tables, so it replaces them. Nothing
detects anything; load order settles it. Enable it after MBGA and after the mod it is for.

You can also skip the separate patch and put the generated files straight into your own mod,
declaring MBGA as a dependency so yours loads after it. Same files, one fewer thing for your
players to enable.

If your mod ships map files but has not actually moved any border, the tool says so and builds
nothing.

Run without an argument, it regenerates MBGA's own tables for the base game's map — do that
after a game update that changes the map.

Needs `pillow` and `numpy`.

---

## Using it from your own mod

Everything below is meant to be called from outside. Anything not listed here is internal:
it can change or disappear between versions without notice.

Test with the trigger `mbga_is_active`, which follows the CMF convention.

### Opening a state

```
# state scope, scope:actor is the country demanding
scope:some_state = { mbga_open_for_state_effect = yes }
```

Or from the interface, as a scripted GUI:

```
GetScriptedGui('mbga_open_for_state').Execute(
    GuiScope.SetRoot(State.MakeScope).AddScope('actor', GetPlayer.MakeScope).End)
```

Afterwards the global list `mbga_candidates` holds one container per province of that state.

### Reading a candidate

| On the container | Meaning |
| --- | --- |
| `mbga_province` | The province it wraps. |
| `mbga_owner` | Who held it when the state was opened, so it can be handed back. |
| `mbga_hub` | 1 city, 2 port, 3 farm, 4 mine, 5 wood, absent otherwise. |
| `mbga_label` | A flag naming the hub, for localization. |
| `mbga_taken` | Taken during this session. |
| `mbga_takeable` | May be taken right now. |
| `mbga_own_from_start` | Already ours before the state was opened. |

Scripted GUIs answering the same, for an interface that cannot read variables directly:
`mbga_container_taken`, `mbga_container_blocked`, `mbga_container_own_from_start`,
`mbga_container_is_city` / `_port` / `_farm` / `_mine` / `_wood` / `_plain`.

### Taking one

```
GetScriptedGui('mbga_take_container').Execute(
    GuiScope.SetRoot(Container.MakeScope).AddScope('actor', GetPlayer.MakeScope).End)
```

Clicking a taken province hands it back. The mod keeps the selection connected on its own.

### Driving the tool

| Scripted GUI | Scope | Does |
| --- | --- | --- |
| `mbga_refresh_countries` | country | Fills `mbga_countries` with every country worth demanding from. |
| `mbga_set_target_country` | country, `actor` | Chooses who is being demanded from. |
| `mbga_has_target_country` | country | Shown once one is chosen. |
| `mbga_close_tool` | country | Puts the tool down and clears the session. |
| `mbga_tool_is_on` | country | Shown when either tool setting is enabled. |
| `mbga_tool_enabled` | country | Shown under the debug panel setting only. |

### Effects worth having on their own

| Effect | Scope | Does |
| --- | --- | --- |
| `mbga_fill_provinces_of_state = { LIST = x }` | state, `scope:actor` | The provinces of that state, into the actor's list `x`. The base game will not do this at all. |
| `mbga_fill_selectable_provinces` | state, `scope:actor` | The same, into `mbga_selectable`. |
| `mbga_transfer_province_to_taker` | province, `scope:mbga_taker` | Moves one province without naming it. |
| `mbga_ensure_province_index` | any | Builds the index if it is not there. Cheap once built. |
| `mbga_fill_country_list` | country | Every country that exists, is not us, and holds land. |
| `mbga_list_every_province` / `mbga_list_reachable_only` | country | Whether the next state opens with everything takeable or only what borders us. |

Trigger `mbga_province_index_is_ready` says whether the index has been built.

### Replacing the table

`mbga_fill_adjacency_from_table` is an empty effect in the core, replaced through
`REPLACE_OR_CREATE` by the generated module. Replacing it again with your own is supported and
needs no cooperation from this mod — but use `make_compat.py` rather than writing one by hand.

### What is private

`common/scripted_effects/mbga_adjacency.txt` apart from the hook above,
`mbga_containers.txt`, `mbga_border_probe.txt`, `mbga_hubs.txt`, the probe countries `MBG`,
`MBH` and `MBT` with their culture and country type, and every variable whose name begins
`mbga_adj_`, `mbga_pairs_`, `mbga_ops_` or `mbga_probe_`. Do not call into these, and do not
count on the MBG/MBH/MBT tags being free.

---

## FAQ

### Does it overwrite any base game file?

No. Not one. The panel is mounted through `gui/scripted_widgets`, the on action is added to
`on_game_started` rather than replacing it, and everything else is new files.

### Will it conflict with another mod?

Only if that mod claims the country tags `MBG`, `MBH` or `MBT`, or defines something else
called `mbga_*`. A mod that changes the map does not conflict — see
[Building a table](#building-a-table-for-a-redrawn-map).

### The tool does nothing, or the log says `create_country effect [ Invalid tag ]`

MBGA is loaded too early. Move it below every other mod in the playset — see
[Load it last](#load-it-last).

This is what a mod's `replace_paths` does: it claims a whole folder, and the game then reads
that folder only from it, dropping what every mod loaded before it put there. MBGA overwrites
nothing, and it makes no difference: `common/country_definitions` claimed by someone else
takes the probe countries with it, and `common/decisions` takes the bench.

Loading last costs nothing, since MBGA overwrites nothing to begin with.

### Do I need a compatibility patch to play with a total conversion?

Both answers are true. **No** — the mod works on any map without one: it asks the engine
province by province, which is correct everywhere. **Yes** — on a large state that is slow
enough to feel, and a table is what removes the wait.

There are two ways to have the table. A mod that redraws the map can generate it and ship it
itself, declaring MBGA as a dependency; then nothing else is needed. Otherwise someone builds
a separate patch with the same tool. Either way it is the same generated files.

### Does it disable achievements?

No. Verified in game: achievements stay on.

### Multiplayer?

Untested. The mod declares itself multiplayer synchronized and holds its state in country
variables and containers, which are game state and travel with the session. Expect trouble if
provinces are taken while the game is running; take them on pause.

### Can I add it to a game in progress?

Yes. The index is built at the start of a game, and rebuilt on demand when it is missing.
Taking it out again mid-save will not affect the rest of the game either: what it leaves
behind is variables and containers that nothing reads once the mod is gone, and the provinces
stay where they were put.

### What does taking a province cost the state it came from?

Building **levels** survive: they are what they were. What does not survive is who works in
them — the buildings come out empty and refill over time. A company headquarters can also go,
since it is a building like any other: `building_company_headquarter` is engine-placed, stands
at the state's city hub, and moves or disappears with the ground under it. The company itself
belongs to the country, not to the territory, and is not lost with the province.

None of that can be undone from script. Nothing in the engine touches employment, and the
headquarters is `buildable = no`, so it is not something a mod may place. A building hires
again from the pops of its own state over the following weeks.

The reason is that Victoria 3 has no notion of handing over a province. Giving it to a
throwaway country and annexing that country away is the only thing the engine offers that
moves one, so a province transfer costs what an annexation costs. It is the least bad of the
options rather than a good one, and if the game ever offers a way to move a province outright,
this is the first thing that goes.

### Why do the probe countries appear in the interest group error log?

Raising a country produces interest group errors of its own accord. They are harmless, and the
countries are annexed away in the same effect chain.

### How large is the table, and why?

About 19 MB of script, 230 000 entries. It is one line per province pair because there is no
other way to store a neighbour list the engine can read back.
