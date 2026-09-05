#!/usr/bin/env python3
"""The geographic region keys the mod tries when it has to walk an unfamiliar map.

every_province_in_<short_key> is the only thing in the game that hands out province scopes,
and it exists only for geographic regions declared in script. The key is part of the effect
name, fixed when the game loads, so it cannot be built from anything the mod learns while
running. What can be done is to try the keys that exist, and an effect naming a region that is
not there is thrown out on its own without touching the others.

So this collects the keys that could ever be needed: the base game's, and those of every
installed mod that redraws the map and is not already covered by old_world and new_world.
A mod that plays on the base game's map contributes nothing however many regions it declares,
since its provinces are reachable through the base game's own names - most of what a flavour
mod declares is a subset of a vanilla region, used to aim an event.

What comes out is a list of names - not a list of provinces, states or regions - and a map
nobody here has seen still works if it names its regions conventionally.

Run: python tools/bake_known_worlds.py [--write]
"""
import glob
import io
import os
import re
import sys

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vic3_map import MapSource, find_game, read  # noqa: E402

NL = '\n'
T = '\t'
GEO = os.path.join('common', 'geographic_regions')
BLOCK = re.compile(r'^([a-z_][a-z0-9_]*)\s*=\s*\{', re.M)
SHORT = re.compile(r'short_key\s*=\s*"([^"]+)"')

# Walked first and on their own, since between them they are the whole land map of the base
# game and of anything built on its region names.
WORLD = ('old_world', 'new_world')

# A region with no land under it would only cost a pass that files nothing.
SKIP = ('water', 'unreleased')


def workshop_dirs():
    """Every installed Victoria 3 workshop mod, wherever Steam put it."""
    out = []
    for drive in 'CDEFGH':
        for base in (r'%s:\Steam', r'%s:\SteamLibrary', r'%s:\Program Files (x86)\Steam'):
            p = os.path.join(base % drive, 'steamapps', 'workshop', 'content', '529340')
            if os.path.isdir(p):
                out += [os.path.join(p, d) for d in sorted(os.listdir(p))]
    return out


def keys_in(base):
    """short_key -> True for every geographic region declared under base."""
    out = []
    for f in sorted(glob.glob(os.path.join(base, GEO, '*.txt'))):
        text = io.open(f, encoding='utf-8-sig', errors='replace').read()
        for m in BLOCK.finditer(text):
            body = text[m.end():]
            end = body.find(NL + '}')
            k = SHORT.search(body[:end if end > 0 else None])
            if k:
                out.append(k.group(1))
    return out


def mod_name(path):
    """What the mod calls itself, or its workshop id if it says nothing."""
    meta = os.path.join(path, '.metadata', 'metadata.json')
    if os.path.isfile(meta):
        m = re.search(r'"name"\s*:\s*"([^"]+)"',
                      io.open(meta, encoding='utf-8-sig', errors='replace').read())
        if m:
            return m.group(1)
    return os.path.basename(path)


def geographic_regions(source):
    """short_key -> the state regions it holds, on the map this source describes."""
    strategic = {}
    for path in source.script_files(os.path.join('common', 'strategic_regions')).values():
        text = read(path)
        for m in BLOCK.finditer(text):
            body = text[m.end():]
            end = body.find(NL + '}')
            st = re.search(r'states\s*=\s*\{([^}]*)\}', body[:end if end > 0 else None], re.S)
            if st:
                strategic[m.group(1)] = st.group(1).split()

    out = {}
    for path in source.script_files(GEO).values():
        text = read(path)
        for m in BLOCK.finditer(text):
            body = text[m.end():]
            end = body.find(NL + '}')
            b = body[:end if end > 0 else None]
            k = SHORT.search(b)
            if not k:
                continue
            states = set()
            sr = re.search(r'strategic_regions\s*=\s*\{([^}]*)\}', b, re.S)
            for name in (sr.group(1).split() if sr else []):
                states |= set(strategic.get(name.replace('sr:', ''), []))
            st = re.search(r'state_regions\s*=\s*\{([^}]*)\}', b, re.S)
            states |= set(st.group(1).split() if st else [])
            out[k.group(1)] = states
    return out


def uncovered_by_world(source):
    """The land state regions old_world and new_world do not reach on this map.

    A mod whose map they cover entirely needs none of its own names: the second rung of the
    walk finishes it, and its keys would only be tried on a map they mean nothing on."""
    regions = source.state_regions()
    water = source.water()
    land = {n for n, r in regions.items()
            if any(int(p[1:], 16) not in water for p in r['provinces'])}
    geo = geographic_regions(source)
    reached = set()
    for k in WORLD:
        reached |= geo.get(k, set())
    return land - reached


def collect():
    """-> [(source, [keys])], the base game first, then a group per mod.

    Grouped rather than sorted as one list, so that a mod's regions stand together and a
    reader can see at a glance which map each name came from. A key already taken by an
    earlier source is left there: only the first sighting names it."""
    taken = set(WORLD) | set(SKIP)
    groups = []

    def add(source, keys):
        fresh = sorted({k for k in keys if k not in taken})
        if fresh:
            groups.append((source, fresh))
            taken.update(fresh)

    game = find_game()
    if game:
        add('base game', keys_in(game))

    for d in workshop_dirs():
        if not os.path.isdir(os.path.join(d, GEO)):
            continue
        source = MapSource(game, d)
        if not source.redrawn():
            continue                       # plays on the base game's map, so nothing new
        if not uncovered_by_world(source):
            continue                       # old_world and new_world already reach all of it
        add(mod_name(d), keys_in(d))
    return groups


HEAD = """# Generated by tools/bake_known_worlds.py - do not edit by hand.
# Source: common/geographic_regions of the base game and of the mods installed when it ran.

# Geographic region keys to try on a map the mod cannot otherwise walk.
#
# These are names, not map data. Nothing here says which provinces, states or regions exist.
#
# The work is written once, in common/scripted_effects/mbga_province_index.txt, and each key
# below only names itself. A key still needs an effect of its own: the key is part of the
# effect name, so one naming a region this map does not declare is thrown out whole, and would
# take every other key with it if they shared an effect.

"""


def bake(groups):
    out = [HEAD]
    for source, keys in groups:
        out.append(NL + '# ' + source + NL)
        for k in keys:
            out.append('mbga_walk_%s = { mbga_walk_one_region = { REGION = %s } }' % (k, k) + NL)

    out.append(NL + '# Tried in turn, and abandoned the moment the index holds the whole map,'
               + NL + '# so a map answered earlier pays for nothing here.' + NL)
    out.append('mbga_walk_known_worlds = {' + NL)
    for source, keys in groups:
        out.append(T + '# ' + source + NL)
        for k in keys:
            out.append(T + 'mbga_walk_unless_complete = { REGION = %s }' % k + NL)
    out.append('}' + NL)
    return ''.join(out)


def main():
    groups = collect()
    for source, keys in groups:
        print('%-46s %d' % (source[:46], len(keys)))
    print(NL + '%d keys in all, from %d sources'
          % (sum(len(k) for _, k in groups), len(groups)))

    if '--write' not in sys.argv:
        print(NL + 'run again with --write to generate the list')
        return 0
    path = os.path.join(MOD, 'common', 'scripted_effects', 'mbga_known_worlds.txt')
    io.open(path, 'w', encoding='utf-8-sig', newline=NL).write(bake(groups))
    print('wrote %s' % os.path.relpath(path, MOD))
    return 0


if __name__ == '__main__':
    sys.exit(main())
