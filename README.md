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
folder from it alone, ignoring what every mod loaded **before** it put there - file names and
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
| The provinces of a state | There is no province iterator on a state. `every_province` demands a *province* scope as an effect, and the only iterator that yields provinces at all is `every_province_in_<geographic region>`. As a *script value* it does walk a state, but a script value returns numbers, never scopes. |
| A province by number, or a province's neighbours | Neither exists. A province can be reached only through `p:xRRGGBB` written out in full, or from a battle. |
| Whether two provinces touch | Nothing asks it. The nearest thing is a question about their *states*. |
| A variable on a province | Provinces do not support variables. State regions do. |
| A province's position | Not readable in script, and not readable in the interface either. |
| Which province is a state's city, port, farm, mine or wood hub | Declared in the map data, never readable back. |
| Moving a province | `set_owner_of_provinces` takes literal ids only. Nothing moves a province held in a scope. |
| A map mode that computes something | `map_painting_mode` is an engine enum. There is no hook. |
| An effect named by a variable | `$PARAM$` is filled in when the game loads, long before a variable has a value. It can name a variable, a flag or an effect to call, but not one the engine resolves as it reads the file. |

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

1. a generated index, if a module for this map is loaded - exact, and costs no walking;
2. `old_world` and `new_world`, which between them are the base game's whole land map, and
   that of anything keeping its region names - Anbennar included;
3. every other key that could ever be needed, from
   `common/scripted_effects/zz_mbga_known_worlds.txt`, tried one at a time. That list holds the
   base game's names and those of installed mods that both redraw the map *and* put land
   somewhere `old_world` and `new_world` do not reach - a mod that plays on the base game's
   map contributes nothing, however many regions it declares for its own events.

It knows when to stop by asking the map, not by counting: nothing is left to do once every
state region that holds a state has its provinces filed. A walk that reached only part of the
map cannot pass for a whole one, and the mod says so in the log rather than quietly listing
less than there is.

Should a state ever turn up with nothing filed, the index is built again there and then. A
region that comes back empty a second time is remembered and not asked about again.

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
province transfers per province - which is what makes a large state slow.

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
sweep never runs there again. That the neighbour lists reach past the region's own edge - which
only a table can say, since probing finds neighbours only among the provinces on offer - means
no province need be lent out to ask whether it borders you.

So on a map with no table the first opening of a region is the expensive one, and every
opening after it is cheaper; on a map with one, none of them costs anything.

### The courier

`set_owner_of_provinces` only takes ids written out in full, which is no use when the province
is a scope. So the province is given to a throwaway country of its own, and the receiver
annexes that country immediately. Three such countries exist - two for asking about borders,
one for carrying - and none is ever seen: they are raised and removed inside one effect chain.

This is where the mod costs the player something, because the engine has no notion of handing
over a province: an annexation is what it gives you, so a transfer costs what an annexation
costs. Building levels come through it intact; their workforce and any Company Headquarters do
not. See the [FAQ](#what-does-taking-a-province-cost-the-state-it-came-from).

### Ground nobody can march through

About a fifth of the land is impassable - 7699 provinces on the base game's map, mountain and
ice and a good deal of plain that the map simply closes off. They belong to a state like any
other province, so they can be demanded, but they follow two rules of their own.

**Reach runs one way through them.** You can take a mountain from the valley beside it, but
taking it opens nothing beyond: a range is not a road. Otherwise you could step across a
mountain wall into land you never bordered.

**They come as a set.** Taking one takes every impassable province in that state, and handing
one back returns all of them. They hold nothing and are worth nothing, so there is no reason
to choose among them - and one left behind by accident is a trap, since no army can reach it
and no later war can take it.

Nothing in script can tell an impassable province from any other. There is no trigger for it,
and the terrain is no guide - the base game has over a thousand impassable provinces of plain.
Only the state region files say so, so this needs a generated table; without one they are
treated as ordinary ground.

### Staying connected

Provinces are taken one at a time, and each one has to touch either your own land or something
you have already taken in this session. Handing a province back can cut another one off from
your border; when that happens the stranded province is handed back too.

---

### Winning a state, then drawing the border

The war goal **Demand Provinces** asks for a state, the way every territorial war goal does.
What it does not do is take the state: when the peace is signed, a popup comes up for each
state won, and its one option puts the province tool on that state. You draw the border by
hand, close the tool, and the next popup is waiting.

Infamy is charged **afterwards, for what was actually taken** - the share of the state you
kept, out of the state's own price, which is what a conquest would have paid for all of it.
Nothing is charged when the goal is added, because charging up front and refunding the rest
cannot work: infamy decays while a war runs, so by the peace there may be nothing left to give
back.

Ground nobody can march through is free, and does not make the rest any cheaper either: it is
left out of both halves of the sum, so a state that is half mountain still costs its full
price for the half worth having. **On a map with no generated table this cannot be done** -
nothing there knows which provinces those are, and they are charged like any other.

An AI cannot open the tool, so under the AI rule it draws its border in script instead, and it
is held to the same rule as a player: it never reaches ground it does not border. What shape
it cuts depends on who is ruling.

| Ruler | What it takes |
| --- | --- |
| `direct` | A corridor straight to the town, one province wide |
| a naval commander, `dockyard_master` | A corridor to the port |
| `ruthless`, `pillager` | A corridor to the mine |
| `mountain_commander`, `meticulous` | Everything up to the first impassable ground, so the border ends on a ridge |
| `arrogant` | Half the state |
| anyone else | Rings out from the border, one for each of `imperious`, `ambitious`, `arrogant` and `reckless`, and only ever one for `cautious` |

None of this knows where a province lies. There are no coordinates in script, so the shapes
are grown from what touches what rather than drawn on a map, and a corridor is found by
measuring how far each province is from the border and then walking back down the numbers.

Whatever the shape, anything left cut off from home is handed back, exactly as it would be for
a player.

Without a lookup table nothing is known past the state's own edge, so an AI takes the border
ring and no more rather than probing its way inwards during the peace.

## Game rules

| Rule | Settings | What it does |
| --- | --- | --- |
| **Province Demands** | Bordering only *(default)* / Anywhere in the state | Whether a province has to touch land you hold. |
| **Province Transfer Tool** | Off *(default)* / Diplomatic action / Debug panel | How the tool is reached. Off means provinces change hands through war only. |
| **AI Province Demands** | Players only *(default)* / AI may demand too | Whether an AI may take the Demand Provinces war goal. It cannot pick provinces, so it takes the whole state. |
| **Province Scanning** | Short waits / Balanced *(default)* / Fewest interruptions | How much work a state may cost when it opens. **Does nothing on any map the mod has a table for**, which includes the base game's. It is there for a mod that redraws the map and ships no table of its own. |

The first two are read in `common/scripted_guis` and nowhere deeper. The mechanism itself
never asks what the game permits.

---

## Building a patch for a redrawn map

```
python tools/make_compat.py "C:/path/to/your mod"
```

That is the whole job. It reads your mod's map the way the game does - `provinces.png`,
`province_terrains.txt`, `default.map`, `adjacencies.csv`, `map_data/state_regions`,
`common/strategic_regions`, and `replace_paths` if you use it - and writes a finished
compatibility mod next to your folder: metadata, dependencies and three tables, nothing left
to fill in.

The three are the province index, which states hold which provinces; the adjacency table,
which provinces touch which; and the hub table, which province is each state's city, port,
farm, mine and wood.

**Whether you need it depends on your map.** MBGA reaches most redrawn maps on its own by
trying region names, and then a patch is only about speed: without one it asks the engine
which provinces border which, one at a time, which is slow on a large state. But a map whose
states sit in no geographic region cannot be reached at all, and there the index in the patch
is what makes the mod work. `tools/README.md` has the measurements, mod by mod.

The output carries the **same file names** as MBGA's own tables, so it replaces them. Nothing
detects anything; load order settles it. Enable it after MBGA and after the mod it is for.

You can also skip the separate patch and put the generated files straight into your own mod,
declaring MBGA as a dependency so yours loads after it. Same files, one fewer thing for your
players to enable.

If your mod ships map files but has not actually moved any border, the tool says so and builds
nothing.

Run without an argument, it regenerates MBGA's own tables for the base game's map - do that
after a game update that changes the map.

Needs `pillow` and `numpy`.

Every tool, and a table of what has been tested against which mods, is in
[tools/README.md](tools/README.md).

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

Two triggers go with the index: `mbga_province_index_is_ready` says whether it has been
built, `mbga_province_index_is_complete` whether it reaches every state on the map. A map it
does not reach in full is not an error - those states simply list nothing - so ask the second
before relying on a state you did not open yourself.

### Replacing a table

Two effects in the core are empty on purpose and exist to be replaced through
`REPLACE_OR_CREATE`: `mbga_fill_index_from_table`, which files every province under its state
region, and `mbga_fill_adjacency_from_table`, which fills in which province touches which.
Replacing either needs no cooperation from this mod. Use `make_compat.py` rather than writing
one by hand.

A file that replaces one of these must be read after the effect it calls, since the game reads
a folder in name order and an effect naming one that has not been declared yet is discarded
without a word. That is what the `zz_` prefix on the generated files is for.

### What is private

`common/scripted_effects/mbga_adjacency.txt` apart from the two hooks above,
`mbga_containers.txt`, `mbga_border_probe.txt`, `mbga_hubs.txt`, everything named
`mbga_walk_*`, the generated `mbga_baked_*` and `zz_mbga_*` files, the probe countries `MBG`,
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
called `mbga_*`. A mod that changes the map does not conflict - see
[Building a patch](#building-a-patch-for-a-redrawn-map).

### The tool does nothing, or the log says `create_country effect [ Invalid tag ]`

MBGA is loaded too early. Move it below every other mod in the playset - see
[Load it last](#load-it-last).

This is what a mod's `replace_paths` does: it claims a whole folder, and the game then reads
that folder only from it, dropping what every mod loaded before it put there. MBGA overwrites
nothing, and it makes no difference: `common/country_definitions` claimed by someone else
takes the probe countries with it, and `common/decisions` takes the bench.

Loading last costs nothing, since MBGA overwrites nothing to begin with.

### Do I need a compatibility patch to play with a total conversion?

It depends on the map, and the honest answer is measured rather than guessed -
`tools/README.md` has it mod by mod.

**Usually no.** MBGA reaches most redrawn maps on its own, by trying the region names it
knows. Then a patch only removes a wait: without one the mod asks the engine which provinces
border which, one province at a time, which is slow on a large state.

**Sometimes yes, to work at all.** Listing the provinces of a state takes a geographic region,
and a mod only declares the regions its own events need. A map with states in no region cannot
be reached by any name - Victorian Azeroth declares none at all - and there the province index
in the patch is what makes the mod work.

Either way the files are the same, and there are two ways to have them: a mod that redraws the
map can generate them and ship them itself, declaring MBGA as a dependency, or somebody builds
a separate patch with the same tool.

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
them - the buildings come out empty and refill over time. A company headquarters can also go,
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

### Why is the mod so large?

About 23 MB, nearly all of it the generated tables: 230 000 lines of adjacency, one per pair
of provinces that touch, and 40 000 for the index, one per province. Neither can be stored any
more tightly, because the only way to name a province in script is to write its id out.
