#!/usr/bin/env python3
"""Make a mod that redraws the map work with Make Borders Great Again, in one command.

    python tools/make_compat.py "C:/.../mod/Some Total Conversion"

That is the whole job. It reads the mod's map the way the game does, works out which
provinces each state region holds, which of them touch which, and which is each region's hub,
and writes a finished compatibility mod next to it: metadata, dependencies, tables, nothing
left to fill in.

Without a path it regenerates MBGA's own tables in place, for the base game's map.

What comes out replaces MBGA's tables by carrying the same file names, so only one table is
ever loaded and the load order settles which. Nothing needs to detect anything.

A compatibility mod is not required for MBGA to run on a redrawn map: without one the mod
asks the engine province by province, which is correct everywhere and slow on large states.
The table is what makes it free.

Needs Pillow and numpy: python -m pip install pillow numpy
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bake_adjacency                                        # noqa: E402
import bake_hubs                                             # noqa: E402
import bake_index                                            # noqa: E402
from vic3_map import MapSource, find_game, mod_identity      # noqa: E402

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MBGA_ID = 'mbga.province.demands'
MBGA_NAME = 'Make Borders Great Again'


def slug(text):
    """A mod name to something that can sit in an id and a folder name."""
    out = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return out or 'map'


def metadata(name, mod_id, version):
    """The compatibility mod's own metadata, declaring what it needs loaded before it."""
    needs = [{'rel_type': 'dependency', 'id': MBGA_ID, 'display_name': MBGA_NAME,
              'resource_type': 'mod', 'version': '*'}]
    if mod_id:
        needs.append({'rel_type': 'dependency', 'id': mod_id, 'display_name': name,
                      'resource_type': 'mod', 'version': '*'})
    return {
        'name': 'MBGA compatibility: ' + name,
        'id': 'mbga.compat.' + slug(name),
        'version': version,
        'game_id': 'victoria3',
        'supported_game_version': '1.14.*',
        'short_description': 'Province adjacency and hub tables for %s, so Make Borders '
                             'Great Again needs no probing on its map.' % name,
        'tags': ['Utilities', 'Map'],
        'relationships': needs,
        'game_custom_data': {'multiplayer_synchronized': True},
    }


def write_all(root, files):
    for rel, text in sorted(files.items()):
        path = os.path.join(root, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8-sig', newline='\n') as f:
            f.write(text)
    return sum(len(t.encode('utf-8')) for t in files.values())


def same_as_ours(rel, text):
    """Whether MBGA already ships exactly this file."""
    path = os.path.join(MOD, *rel.split('/'))
    if not os.path.isfile(path):
        return False
    with open(path, encoding='utf-8-sig') as f:
        return f.read().replace('\r', '') == text


def own_tables(game):
    """MBGA's own tables, rewritten in place for the base game's map."""
    source = MapSource(game)
    files = {}
    files.update(bake_index.build(source))
    files.update(bake_adjacency.build(source))
    files.update(bake_hubs.build(source))
    size = write_all(MOD, files)
    print('\n%d files, %.1f MB, written into the mod' % (len(files), size / (1024 * 1024)))
    return 0


def compat_for(game, target, out_dir=None):
    name, mod_id = mod_identity(target)
    if not name:
        name = os.path.basename(os.path.normpath(target))
        print('no metadata found, going by the folder name: %s' % name)

    source = MapSource(game, target)
    redrawn = source.redrawn()
    if not redrawn:
        print('%s does not touch map_data, so it plays on the base game\'s map and the '
              'table already in MBGA covers it. Nothing to build.' % name)
        return 0
    print('%s replaces %d map file(s), among them %s'
          % (name, len(redrawn), ', '.join(os.path.basename(r) for r in redrawn[:3])))

    files = {}
    files.update(bake_index.build(source))
    files.update(bake_adjacency.build(source))
    files.update(bake_hubs.build(source))

    # A mod can ship map files without moving a single border - a new strait, a renamed
    # region. Then the tables come out the same as the ones already in MBGA.
    if all(same_as_ours(rel, text) for rel, text in files.items()):
        print('\nThe tables come out identical to the ones MBGA already ships: this mod '
              'changes map files but not which province touches which. Nothing to build.')
        return 0

    meta = metadata(name, mod_id, '1.0.0')
    files['.metadata/metadata.json'] = json.dumps(meta, indent='\t', ensure_ascii=False) + '\n'

    out = out_dir or os.path.join(os.path.dirname(os.path.normpath(target)),
                                  'MBGA compatibility - ' + name)
    size = write_all(out, files)
    print('\n%d files, %.1f MB' % (len(files), size / (1024 * 1024)))
    print('written to %s' % out)
    print('\nEnable it after %s and after the mod it is for. It carries the same file names '
          'as MBGA\'s own tables, so it replaces them.' % MBGA_NAME)
    if not mod_id:
        print('The mod declares no id, so it could not be listed as a dependency: order the '
              'playset by hand.')
    return 0


def main(argv):
    game = find_game()
    if not game:
        print('Victoria 3 not found. Set VIC3_GAME to the game folder.')
        return 2

    args = [a for a in argv[1:] if not a.startswith('-')]
    if not args:
        return own_tables(game)
    target = args[0]
    if not os.path.isdir(target):
        print('no such folder: %s' % target)
        return 2
    return compat_for(game, target, args[1] if len(args) > 1 else None)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
