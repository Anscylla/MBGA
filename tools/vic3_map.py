#!/usr/bin/env python3
"""Where the map comes from: the base game, or a mod that redraws it.

A mod does not patch the map, it replaces files wholesale. provinces.png and
province_terrains.txt are single files, so a mod that ships one has replaced it entirely,
while map_data/state_regions is a folder where a mod's file replaces the base game's file of
the same name and any other name is added to it - unless the mod lists that folder in
replace_paths, which tells the game to read it from the mod alone. A total conversion does
exactly that, and without honouring it the base game's map would be read on top of its own.

This reads a mod the way the game does, falling back to the base game for everything the mod
does not carry.

Used by make_compat.py and by every bake_*.py. Nothing in the mod itself depends on it.
"""
import os
import re

MAP_DATA = 'map_data'
REGIONS = os.path.join(MAP_DATA, 'state_regions')
DEFAULT = os.path.join(MAP_DATA, 'default.map')
TERRAINS = os.path.join(MAP_DATA, 'province_terrains.txt')
WATER_TERRAIN = ('ocean', 'lakes', 'lake')
HEX = re.compile(r'x[0-9A-Fa-f]{6}')
# The game writes hub ids quoted in some files and bare in others.
QUOTED_HEX = re.compile(r'"?(x[0-9A-Fa-f]{6})"?')
HUBS = ('city', 'port', 'farm', 'mine', 'wood')


def find_game():
    for base in (os.environ.get('VIC3_GAME'),
                 r'C:\Steam\steamapps\common\Victoria 3\game'):
        if base and os.path.isdir(os.path.join(base, 'map_data')):
            return base
    for drive in 'CDEFGH':
        p = f'{drive}:\\Steam\\steamapps\\common\\Victoria 3\\game'
        if os.path.isdir(os.path.join(p, 'map_data')):
            return p
    return None


def read(path):
    return open(path, encoding='utf-8-sig', errors='replace').read().replace('\r', '')


def parse_region_text(text, filename=''):
    """One state_regions file -> {state_region: {'provinces', 'hubs', 'file'}}"""
    out = {}
    # strip comments outside quotes
    clean = []
    for line in text.split('\n'):
        q, buf = False, ''
        for ch in line:
            if ch == '"':
                q = not q
            if ch == '#' and not q:
                break
            buf += ch
        clean.append(buf)
    text = '\n'.join(clean)

    depth, cur, body = 0, None, []
    for line in text.split('\n'):
        if depth == 0:
            m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*\{', line)
            if m:
                cur, body = m.group(1), []
        if cur:
            body.append(line)
        depth += line.count('{') - line.count('}')
        if cur and depth == 0:
            blob = '\n'.join(body)
            pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', blob, re.S)
            provs = QUOTED_HEX.findall(pm.group(1)) if pm else []
            hubs = {}
            for h in HUBS:
                hm = re.search(r'^\s*' + h + r'\s*=\s*"?(x[0-9A-Fa-f]{6})"?', blob, re.M)
                if hm:
                    hubs[h] = hm.group(1)
            # keep the original casing: p: lookups are matched against the
            # ids exactly as the game writes them
            out[cur] = {'provinces': provs, 'hubs': hubs, 'file': filename}
            cur = None
    return out


def parse_terrain_text(text):
    """-> {province_id: terrain}"""
    out = {}
    for line in text.split('\n'):
        m = re.match(r'^\s*(x[0-9A-Fa-f]{6})\s*=\s*"?([a-z_]+)"?', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


class MapSource:
    """The map as the game would see it with this mod loaded."""

    def __init__(self, game, mod=None):
        self.game = game
        self.mod = mod
        self.replaced = replace_paths(mod) if mod else []
        self._regions = None
        self._terrain = None
        self._default = None

    def replaces(self, folder):
        """A total conversion names folders in replace_paths, and the game then reads only
        its own copies of them. Without this a mod that adds its own state regions beside
        the base game's would appear to hold both maps at once."""
        folder = folder.replace('\\', '/')
        return any(folder == r or folder.startswith(r + '/') for r in self.replaced)

    def file(self, rel):
        """The mod's copy of a file if it has one, otherwise the base game's."""
        if self.mod:
            p = os.path.join(self.mod, rel)
            if os.path.isfile(p):
                return p
        return os.path.join(self.game, rel)

    def script_files(self, folder):
        """Filename -> path for a folder of script, read the way the game reads it: the mod's
        copy wins over the base game's file of the same name, any other name is added, and a
        folder the mod claims in replace_paths is read from the mod alone."""
        out = {}
        bases = [self.mod] if self.replaces(folder) else [self.game, self.mod]
        for base in bases:
            if not base or not os.path.isdir(os.path.join(base, folder)):
                continue
            for fn in sorted(os.listdir(os.path.join(base, folder))):
                if fn.endswith('.txt'):
                    out[fn] = os.path.join(base, folder, fn)
        return out

    def region_files(self):
        """The state region files, as the game reads them."""
        return self.script_files(REGIONS)

    def state_regions(self):
        """-> {state_region: {'provinces': [...], 'hubs': {kind: id}, 'file': name}}"""
        if self._regions is None:
            out = {}
            for fn, path in sorted(self.region_files().items()):
                out.update(parse_region_text(read(path), fn))
            self._regions = {n: r for n, r in out.items() if r['provinces']}
        return self._regions

    def terrains(self):
        """-> {province id: terrain}, upper case ids."""
        if self._terrain is None:
            path = self.file(TERRAINS)
            if not os.path.isfile(path):
                raise SystemExit('no map_data/province_terrains.txt to read')
            self._terrain = {k.upper(): v for k, v in parse_terrain_text(read(path)).items()}
        return self._terrain

    def default_map(self):
        """map_data/default.map, which names the other map files and lists the water."""
        if self._default is None:
            self._default = read(self.file(DEFAULT))
        return self._default

    def named_file(self, key, fallback):
        """A map file under the name default.map gives it, since a mod may rename it."""
        m = re.search(r'^\s*' + key + r'\s*=\s*"([^"]+)"', self.default_map(), re.M)
        return os.path.join(MAP_DATA, m.group(1) if m else fallback)

    def water(self):
        """Province ids nobody can own, as numbers.

        default.map lists them outright, in sea_starts and lakes, which is the engine's own
        answer. The terrain file is only a fallback for a mod whose default.map cannot be
        read, and it names lakes differently between versions."""
        out = set()
        for block in ('sea_starts', 'lakes'):
            m = re.search(block + r'\s*=\s*\{([^}]*)\}', self.default_map(), re.S)
            if m:
                out |= {int(p[1:], 16) for p in HEX.findall(m.group(1))}
        if out:
            return out
        t = self.terrains()
        return {int(p[1:], 16) for r in self.state_regions().values() for p in r['provinces']
                if t.get(p.upper()) in WATER_TERRAIN}

    def impassable(self):
        """Province ids nobody can march through, as numbers.

        A state region lists them outright. Nothing in script can tell one from any other
        province: there is no trigger for it, and the terrain is no guide - the base game's
        map has a thousand impassable provinces of plain."""
        out = set()
        for path in self.region_files().values():
            for m in re.finditer(r'impassable\s*=\s*\{([^}]*)\}', read(path), re.S):
                out |= {int(p[1:], 16) for p in HEX.findall(m.group(1))}
        return out

    def prime_land(self):
        """Province ids the state region calls prime land, as numbers.

        Prime land counts five times an ordinary province towards a state's share of its
        region, and that share is what its arable land and its resource caps are worked out
        from. Nothing in script can see it either: it is map data and no trigger reads it."""
        out = set()
        for path in self.region_files().values():
            for m in re.finditer(r'prime_land\s*=\s*\{([^}]*)\}', read(path), re.S):
                out |= {int(p[1:], 16) for p in HEX.findall(m.group(1))}
        return out

    def straits(self):
        """Pairs that touch across water: straits, and the canals cut through them.

        The pixels cannot show these - the two provinces do not meet anywhere on the map -
        but the game treats them as adjacent, so a table built without them would answer
        differently from the engine."""
        path = self.file(self.named_file('adjacencies', 'adjacencies.csv'))
        if not os.path.isfile(path):
            return []
        out = []
        for line in read(path).split('\n')[1:]:
            f = line.split(';')
            if len(f) > 2 and HEX.fullmatch(f[0].strip()) and HEX.fullmatch(f[1].strip()):
                out.append((int(f[0].strip()[1:], 16), int(f[1].strip()[1:], 16)))
        return out

    def edges(self):
        """Every unordered pair of province colours that meet along a pixel edge."""
        import numpy as np
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None
        a = np.asarray(Image.open(self.file(self.named_file('provinces', 'provinces.png')))
                       .convert('RGB'), dtype=np.uint32)
        packed = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]

        pairs = []
        for one, two in ((packed[:, :-1], packed[:, 1:]),      # side by side
                         (packed[:-1, :], packed[1:, :])):     # one above the other
            differ = one != two
            pairs.append(np.stack((one[differ], two[differ]), axis=1))
        p = np.concatenate(pairs)
        p.sort(axis=1)
        return np.unique(p, axis=0)

    def redrawn(self):
        """Which map files this mod replaces. Empty means it plays on the base game's map
        and needs no table of its own."""
        if not self.mod:
            return []
        out = [rel for rel in (self.named_file('provinces', 'provinces.png'), TERRAINS,
                            DEFAULT, self.named_file('adjacencies', 'adjacencies.csv'))
               if os.path.isfile(os.path.join(self.mod, rel))]
        d = os.path.join(self.mod, REGIONS)
        if os.path.isdir(d):
            out += [os.path.join(REGIONS, fn) for fn in sorted(os.listdir(d))
                    if fn.endswith('.txt')]
        return out


def replace_paths(path):
    """The folders this mod tells the game to read only from itself."""
    meta = os.path.join(path, '.metadata', 'metadata.json')
    if not os.path.isfile(meta):
        return []
    import json
    try:
        d = json.loads(read(meta))
    except ValueError:
        return []
    return [p.replace('\\', '/').strip('/')
            for p in d.get('game_custom_data', {}).get('replace_paths', [])]


def mod_identity(path):
    """-> (name, id). Both may be None: a mod is free to carry neither."""
    meta = os.path.join(path, '.metadata', 'metadata.json')
    if os.path.isfile(meta):
        import json
        try:
            d = json.loads(read(meta))
            return d.get('name'), d.get('id')
        except ValueError:
            pass
    for fn in sorted(os.listdir(path)):        # the older descriptor, still in use
        if fn.endswith('.mod'):
            text = read(os.path.join(path, fn))
            m = re.search(r'^\s*name\s*=\s*"([^"]*)"', text, re.M)
            if m:
                return m.group(1), None
    return None, None


__all__ = ['MapSource', 'find_game', 'mod_identity', 'replace_paths', 'read']
