# Tools

These scripts ship with the mod. They are for anyone who wants MBGA to work on a map it does
not know about - a total conversion, or the base game after a patch that moves borders.

None of them run while the game runs. They read the map off disk and write script files that
the mod loads next time you start it.

They need Python 3. Two of them read `provinces.png` and also need Pillow and numpy:

```
python -m pip install pillow numpy
```

They find Victoria 3 by themselves. If they cannot, set `VIC3_GAME` to the game folder. Run
them from the mod folder.

| Script | What it is for |
| --- | --- |
| `make_compat.py` | Build a compatibility patch for a mod that redraws the map. |
| `bake_known_worlds.py` | Refresh the list of region names after installing a new total conversion. |
| `vic3_map.py` | Shared code. The two above use it; you never run it yourself. |

---

## make_compat.py

This is the one you want. It writes three tables:

| Table | What it holds |
| --- | --- |
| province index | which provinces each state region holds |
| adjacency | which provinces touch which, straits and canals included, and which cannot be marched through |
| hubs | which province is each state's city, port, farm, mine and wood |

```
python tools/make_compat.py "C:/path/to/some mod"
```

Point it at a mod that changes the map. It reads that mod's map exactly the way the game does
and writes a finished compatibility mod in the folder next to it: metadata, dependencies and
the three tables, with nothing left to fill in. Enable it after MBGA and after the mod it is
for.

Without a patch MBGA still works on most redrawn maps, but every time you open a state it has
to ask the game which provinces border which, one province at a time. On a large state that is
slow enough to notice. The patch makes it instant, and on a map MBGA cannot walk at all - see
the table below - it is what makes the mod work in the first place.

Run it with no argument and it rebuilds MBGA's own tables for the base game's map. Do that
after a game update that changes the map.

If the mod ships map files but has not actually moved any border, the tool tells you so and
builds nothing.

It reads `provinces.png`, `province_terrains.txt`, `default.map`, `adjacencies.csv`,
`map_data/state_regions` and `common/strategic_regions`, and it honours `replace_paths`.
`bake_index.py`, `bake_adjacency.py` and `bake_hubs.py` do the three parts of the work;
`make_compat.py` calls them, so you do not have to.

---

## bake_known_worlds.py

```
python tools/bake_known_worlds.py           # show what it would collect
python tools/bake_known_worlds.py --write   # write the list
```

Run this after installing a total conversion that MBGA does not list further down this page.
It writes `common/scripted_effects/zz_mbga_known_worlds.txt`.

To list the provinces of a state, MBGA has to walk a geographic region - see
[Compatibility](#compatibility) below for why. It therefore keeps a list of region names to
try. This script builds that list by looking at the base game and at every mod you have
installed.

It only takes names from mods that redraw the map **and** put land somewhere `old_world` and
`new_world` cannot reach. A mod that plays on the base game's map is skipped no matter how
many regions it declares: Morgenröte declares 87 and Better Politics Mod 2, and none of them
can add a single province, because the base game's own names already reach all of it.

What comes out is a list of names and nothing else. It says nothing about which provinces,
states or regions exist.

**It replaces the list, it does not add to it.** Two copies of a name would walk the same
ground twice, so the file is written from scratch every time. Names that shipped with MBGA for
maps you do not have installed go away, and MBGA stops covering those maps. The script tells
you which ones before it writes, so keep a copy of the file first if that matters to you.

---

## vic3_map.py

Shared code, used by both scripts above. You never run it.

Its job is to answer "what does the map look like with this mod enabled?", because that is
harder than reading the mod's folder. The game builds the map from the base game and the mod
together, by three rules:

- a file in the mod replaces the base game's file **of the same name**;
- a file with any other name is **added** to what the base game has;
- unless the mod lists that folder in `replace_paths`, in which case the base game's copy of
  the folder is ignored completely.

Get this wrong and every table built afterwards is wrong too.

Everything else here - provinces, terrain, water, straits, hubs - goes through it.

---

# Compatibility

To offer you the provinces of a state, MBGA has to get a list of them. The game makes that
surprisingly hard: the only thing in it that hands out provinces one by one is
`every_province_in_<region>`, and that exists only for geographic regions someone declared in
a file. The region name is baked into the effect name when the game loads, so MBGA cannot
work it out while playing - it can only try names it already knows.

So it tries them in order and stops as soon as it has the whole map:

1. a generated table, if a compatibility patch is loaded;
2. `old_world` and `new_world`, the base game's two halves;
3. every name in `zz_mbga_known_worlds.txt`.

It knows when to stop by looking at the map: nothing is left to do once every state region
that holds a state has its provinces filed. Each rung says in `debug.log` whether it was
reached and what it left behind, so a map that comes out short can be read straight off the
log.

**The catch:** a geographic region is optional. A mod declares the ones its own events need
and no more, so a map can have states that sit in no geographic region at all.

The state itself is still perfectly reachable: `every_state` and `every_state_region` are
global and name nothing. What cannot be had is a **province scope** inside it, because
`every_province_in_<region>` is the only thing in the game that produces one, and there is no
region to name. Those states behave like any other state; they simply cannot be taken apart.

That is what rung 1 is for, and why `make_compat.py` writes a province index as well as the
two tables: a generated index names every province outright and needs no region at all.

Measured against every mod installed here. "Cascade" is how much of the map MBGA reaches by
name alone.

| Mod | Land regions | `old_world`+`new_world` | Cascade | Out of reach |
| --- | ---: | ---: | ---: | ---: |
| Base game | 675 | 100% | **100%** | - |
| 1776 - Age of Revolutions | 675 | 100% | **100%** | - |
| Basileia Romaion 1736 | 675 | 100% | **100%** | - |
| Cold War Era (1950) | 675 | 100% | **100%** | - |
| Interwar 1910-1960 | 675 | 100% | **100%** | - |
| UNIPOLAR | 675 | 100% | **100%** | - |
| Victorian Century | 675 | 100% | **100%** | - |
| The Pony In The High Castle | 902 | 0% | **100%** | - |
| 1913: The Gathering Storm | 675 | 99% | 99% | 1 |
| Anbennar | 776 | 99% | 99% | 1 |
| Age of Discovery 1444 | 674 | 99% | 99% | 3 |
| Realms of Exether | 752 | 0% | 94% | 40 |
| The New Order Remastered | 715 | 90% | 91% | 61 |
| Beyond Rice and Salt | 668 | 35% | 90% | 64 |
| Cold War Project | 631 | 48% | 89% | 64 |
| Divergences of Darkness | 693 | 7% | 84% | 110 |
| **Victorian Azeroth** | 702 | 0% | **0%** | 702 |

## Where the gaps come from

Every state in the last column sits in **no geographic region at all** on that map. It is not
a name MBGA is missing - there is no region containing it. Checked one by one: Exether's 40
are Ashwick, Blackwood, Aubern Flow and the like; Divergences' 110 include Alsace, Adal and
Alxa; Beyond Rice and Salt's 64 are Andalusia and a run of ocean states.

Those states show no provinces, so nothing in them can be demanded. Everything else about them
is untouched, and the rest of the map works normally.

**Victorian Azeroth is the one map that fails completely**, and for a different reason. It
replaces the map and claims `map_data` and `map_data/state_regions` in `replace_paths`, but
declares no geographic regions of its own. So the base game's 165 get loaded instead, and
every one of them names states that do not exist on Azeroth. No list of names can fix that.

Two entries are worth noting the other way round. **The Pony In The High Castle** is where the
name list earns its keep: the base game's two halves reach none of it, and its own six regions
reach all of it. **UNIPOLAR** redraws the map and is still covered by `old_world` and
`new_world` alone, so none of its 161 names is even collected.

## Closing a gap

More names will not help, because the missing states are in no region to name. The fix is to
skip the walk entirely and hand MBGA the finished list.

MBGA has an empty effect, `mbga_fill_index_from_table`, sitting at the top of the cascade for
exactly this. A compatibility patch replaces it with `REPLACE_OR_CREATE:` and fills the index
outright:

```
REPLACE_OR_CREATE:mbga_fill_index_from_table = {
    s:STATE_ASHWICK ?= {
        add_to_variable_list = { name = mbga_region_provinces target = p:x0AE57A }
        add_to_variable_list = { name = mbga_region_provinces target = p:x0D3025 }
    }
    ...
    set_global_variable = { name = mbga_index_count value = 40823 }
}
```

Every province named outright and filed under its state region. Province ids are literal, so
no geographic region is involved and nothing has to exist for it to work.

`make_compat.py` writes this for you, along with the other tables. It is what makes a map like
Victorian Azeroth work.
