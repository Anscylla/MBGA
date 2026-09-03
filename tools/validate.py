#!/usr/bin/env python3
"""Everything that can be checked without starting the game.

Braces, encoding and indentation; effects, scripted guis, localization keys and game rule
settings that are used but never declared; $PARAM$ inside quoted event target links, where
the game silently resolves a different name; references to base game content that does not
exist; and the rule that the mechanism must not read game rules, which belong to the
interface layer.

Run: python tools/validate.py
"""
import os
import re
import sys

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from verify_map_data import find_game
except ImportError:
    def find_game():
        return None


def uncomment(line):
    quoted = False
    out = ''
    for ch in line:
        if ch == '"':
            quoted = not quoted
        if ch == '#' and not quoted:
            break
        out += ch
    return out


def script_files(*roots):
    for root in roots:
        for dirpath, _, names in os.walk(os.path.join(MOD, root)):
            for name in sorted(names):
                if name.endswith(('.txt', '.gui', '.yml')):
                    yield os.path.join(dirpath, name)


def read(path):
    return open(path, encoding='utf-8-sig', errors='replace').read()


def rel(path):
    return os.path.relpath(path, MOD).replace(os.sep, '/')


def main():
    problems = []

    for path in script_files('common', 'gui', 'localization', '.metadata'):
        if open(path, 'rb').read(3) != b'\xef\xbb\xbf':
            problems.append(f'{rel(path)}: no UTF-8 BOM')
        if path.endswith('.yml'):
            continue

        depth = 0
        for n, line in enumerate(read(path).split('\n'), 1):
            bare = uncomment(line)
            if bare.strip():
                # a block put in the wrong place still balances; the indent gives it away
                want = depth - 1 if bare.strip().startswith('}') else depth
                got = len(line) - len(line.lstrip('\t'))
                if got != want and not line.strip().startswith('#'):
                    problems.append(f'{rel(path)}:{n}: indented {got}, expected {want}')
            depth += bare.count('{') - bare.count('}')
            if depth < 0:
                problems.append(f'{rel(path)}:{n}: closed a brace that was never opened')
                break
        if depth > 0:
            problems.append(f'{rel(path)}: {depth} brace(s) left open')

        # $PARAM$ is not substituted inside a quoted event target link
        for n, line in enumerate(read(path).split('\n'), 1):
            if line.strip().startswith('#'):
                continue
            for quoted in re.finditer(r'"[^"]*"', line):
                if '$' in quoted.group(0):
                    problems.append(f'{rel(path)}:{n}: $PARAM$ inside quotes, '
                                    f'the game reads a different name: {quoted.group(0)[:50]}')

    # set_variable assigns, change_variable does arithmetic. Writing add = on a set_ effect
    # is accepted quietly and simply does not happen.
    for path in script_files('common'):
        for n, line in enumerate(read(path).split(chr(10)), 1):
            m = re.search(r'(set_(?:global_|local_)?variable) = \{[^}]* (add|subtract|multiply|divide) =', line)
            if m:
                problems.append(f'{rel(path)}:{n}: {m.group(1)} takes value =, not {m.group(2)} =; use change_variable for arithmetic')

    # a diplomatic action's effect block is accept_effect; a plain effect block parses and
    # is never run
    for path in script_files('common'):
        if 'diplomatic_actions' not in path:
            continue
        for n, line in enumerate(read(path).split(chr(10)), 1):
            if re.match(r'	?effect = ' + chr(123) + '$', line):
                problems.append(f'{rel(path)}:{n}: a diplomatic action runs accept_effect, '
                                f'never effect')

    defined = set()
    for path in script_files('common'):
        if 'scripted_effects' in path:
            defined |= set(re.findall(r'^([a-z_0-9]+) = \{', read(path), re.M))
    called = set()
    for path in script_files('common'):
        # indented, or it is a declaration of its own rather than a call
        called |= set(re.findall(r'^[	 ]+(mbga_[a-z_0-9]+) = (?:yes|\{ *[A-Z])',
                                 read(path), re.M))
    for name in sorted(called - defined):
        problems.append(f'effect {name} is called but never defined')

    guis = set()
    for path in script_files('common'):
        if 'scripted_guis' in path:
            guis |= set(re.findall(r'^([a-z_0-9]+) = \{', read(path), re.M))
    wanted = set()
    for path in script_files('gui'):
        wanted |= set(re.findall(r"GetScriptedGui\('([a-z_0-9]+)'\)", read(path)))
    for name in sorted(wanted - guis):
        problems.append(f'scripted gui {name} is used by the interface but never defined')

    loc = set()
    for path in script_files('localization'):
        loc |= set(re.findall(r'^ ([A-Za-z_0-9]+):', read(path), re.M))
        for n, line in enumerate(read(path).split('\n'), 1):
            if line.strip() and not line.startswith(' ') and not line.startswith('l_'):
                problems.append(f'{rel(path)}:{n}: line belongs to no key')
    keys = set()
    for path in script_files('gui'):
        keys |= set(re.findall(r'text = "(MBGA_[A-Z_0-9]+)"', read(path)))
    for name in sorted(keys - loc):
        problems.append(f'localization key {name} is used by the interface but missing')

    rules = set()
    rule_file = os.path.join(MOD, 'common', 'game_rules', 'mbga_game_rules.txt')
    if os.path.exists(rule_file):
        rules = set(re.findall(r'^\t([a-z_0-9]+) = \{', read(rule_file), re.M))
    used_rules = set()
    for path in script_files('common'):
        used_rules |= set(re.findall(r'has_game_rule = ([a-z_0-9]+)', read(path)))
    for name in sorted(used_rules - rules):
        problems.append(f'game rule setting {name} is asked for but never declared')

    # the mechanism must not know about this mod's own interface
    for path in script_files('common'):
        if 'scripted_effects' in path and 'has_game_rule' in read(path):
            problems.append(f'{rel(path)}: a scripted effect reads a game rule, which '
                            f'belongs to the interface layer, not the API')

    # things a culture, a country definition or a country type points at have to exist,
    # here or in the game. A culture naming a heritage that does not exist simply fails to
    # load, and the only sign of it is countries built on that culture coming out invalid.
    game = find_game()
    if not game:
        problems.append('game not found, cross references to base game content unchecked')
    else:
        def keys_in(*folders):
            found = set()
            for base in (game, MOD):
                for folder in folders:
                    d = os.path.join(base, 'common', folder)
                    if not os.path.isdir(d):
                        continue
                    for dirpath, _, names in os.walk(d):
                        for n in sorted(names):
                            if n.endswith('.txt'):
                                found |= set(re.findall(r'^([A-Za-z_0-9]+) *= *\{',
                                                        read(os.path.join(dirpath, n)), re.M))
            return found

        checks = (
            (r'heritage = ([a-z_0-9]+)', ('discrimination_traits',), 'heritage'),
            (r'language = ([a-z_0-9]+)', ('discrimination_traits',), 'language'),
            (r'trait_group = ([a-z_0-9]+)', ('discrimination_trait_groups',), 'trait group'),
            (r'religion = ([a-z_0-9]+)', ('religions',), 'religion'),
            (r'cultures = \{ ([a-z_0-9]+) \}', ('cultures',), 'culture'),
            (r'country_type = ([a-z_0-9]+)', ('country_types',), 'country type'),
            (r'default_rank = ([a-z_0-9]+)', ('country_ranks',), 'country rank'),
        )
        for pattern, folders, label in checks:
            known = keys_in(*folders)
            for path in script_files('common'):
                for name in set(re.findall(pattern, read(path))):
                    if name not in known:
                        problems.append(f'{rel(path)}: {label} {name} is named but never declared')

    # a texture that is not there shows as a missing icon rather than an error anybody sees
    for path in script_files('common', 'gui'):
        for tex in set(re.findall(r'texture = "(gfx/[^"]+)"', read(path))):
            here = os.path.join(MOD, *tex.split('/'))
            if os.path.exists(here):
                continue
            if game and os.path.exists(os.path.join(game, *tex.split('/'))):
                continue
            problems.append(f'{rel(path)}: texture {tex} is referenced but not present')

    for p in problems:
        print('  ' + p)
    print(f'{len(problems)} problem(s)' if problems else 'all checks passed')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
