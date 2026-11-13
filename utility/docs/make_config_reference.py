"""
Generate docs/config.md, the Configuration Reference, from driver/config.toml.

Every setting's default comes from its value in config.toml, and its description from the comment
on the same line, so improving a comment improves the reference too. A block of comment lines at
the start of a section becomes that section's introduction. Settings that need a driver restart are
the ones Alpaca Pilot asks to restart for (restartKeys in pilot/src/stores/config.ts).

Usage (from the repo root):
    python utility/docs/make_config_reference.py           # write docs/config.md
    python utility/docs/make_config_reference.py --check   # exit 1 if docs/config.md is out of date
"""
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'driver' / 'config.toml'
PILOT_CONFIG = ROOT / 'pilot' / 'src' / 'stores' / 'config.ts'
OUT = ROOT / 'docs' / 'config.md'

KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=')
SECTION = re.compile(r'^\[([a-z_]+)\]')

# Defaults not published in the reference, because they would give away a location
REDACTED = {'location', 'site_latitude', 'site_longitude', 'site_elevation'}

# What each section of config.toml covers, as the introduction to its table
SECTIONS = {
    'network': ('Network', 'How the driver connects to the Benro Polaris, and the services it provides to applications.'),
    'server': ('Site and Equipment', 'Your observing site, GPS receiver, and lens or telescope.'),
    'panorama': ('Panorama', 'The Panorama Grid and the Panel Spacing Calculator. Alpaca Pilot sets most of these from its Panorama pages (see [Creating Panoramas](./panoramas.md)).'),
    'control': ('Control', 'The driver\'s motion control: alignment, tracking, guiding, Periodic Error Correction, the Kalman filter, the PID controller and the motor limits. See the [Control Reference](./control.md) and [Kinematics Reference](./kinematics.md) for how they work.'),
    'models': ('Models', ''),
    'device': ('Aiming', 'Small aiming adjustments.'),
    'logging': ('Logging', 'What the driver writes to its log. Most switches are for diagnosing problems, and can be left as they are.'),
}

HEADER = '''# Configuration Reference
{links}

This page lists every setting of the Alpaca Driver, with its default value. It is generated from the driver's configuration file, `driver/config.toml`, by `utility/docs/make_config_reference.py`: change the file's comments rather than this page.

**Where settings live.** `driver/config.toml` holds the default for each setting, and is replaced when the driver is updated, so don't edit it to change a setting. Instead, change settings in Alpaca Pilot: most are on its Settings page, and some on its PID Tuning, Kalman, Panorama and Dashboard pages. Alpaca Pilot saves the settings you have changed to `data/config.pilot.json`, which the driver applies on top of the defaults each time it starts. Restoring the defaults deletes that file.

**Changing settings from a script.** The `Polaris:ConfigFetch`, `Polaris:ConfigUpdate`, `Polaris:ConfigSave` and `Polaris:ConfigRestore` Device Actions read, change, save and restore settings (see the [Alpaca API Reference](./alpaca-api.md#device-actions)). A change takes effect straight away, except for the settings marked **Restart** below, which need a driver restart.
'''


def comment_start(line: str) -> int:
    """Index of the '#' that starts a line's comment, ignoring any inside quoted strings, or -1."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in '\'"':
            quote = ch
        elif ch == '#':
            return i
    return -1


def restart_keys() -> set[str]:
    """The settings Alpaca Pilot asks for a driver restart after changing."""
    m = re.search(r'const restartKeys = \[(.*?)\]', PILOT_CONFIG.read_text(encoding='utf-8'), re.S)
    return set(re.findall(r"'([a-z_0-9]+)'", m.group(1))) if m else set()


def show_default(value) -> str:
    if isinstance(value, bool):
        return f'`{str(value).lower()}`'
    if isinstance(value, str):
        return f"`'{value}'`"
    if isinstance(value, list):
        return '`[' + ', '.join(f'{v:.3g}' if isinstance(v, float) else str(v) for v in value) + ']`'
    return f'`{value}`'


def parse() -> list[dict]:
    """The sections of config.toml, each with its intro comment block and settings in file order."""
    values = tomllib.loads(CONFIG.read_text(encoding='utf-8'))
    sections, current = [], None
    for line in CONFIG.read_text(encoding='utf-8').split('\n'):
        if m := SECTION.match(line):
            current = {'name': m.group(1), 'intro': [], 'settings': []}
            sections.append(current)
        elif current is None:
            continue
        elif line.startswith('#') and not current['settings']:
            current['intro'].append(line.lstrip('#').strip())
        elif m := KEY.match(line):
            c = comment_start(line)
            current['settings'].append({
                'key': m.group(1),
                'default': values[current['name']][m.group(1)],
                'description': line[c + 1:].strip() if c >= 0 else '',
            })
    return sections


def cell(text: str) -> str:
    """Format a description for a table cell. Quoted values and colon-separated tokens such as
    deg:mm:ss become code, which also stops the site reading ':mm:' as an emoji shortcode."""
    text = re.sub(r"(?<![`\w])('[^'\n]*'|\w+(?::\w+){2,})", r'`\1`', text)
    return text.replace('|', '\\|')


def render() -> str:
    sections = parse()
    restart = restart_keys()
    links = ' · '.join(f'[{SECTIONS[s["name"]][0]}](#{SECTIONS[s["name"]][0].lower().replace(" ", "-")})' for s in sections)
    out = [HEADER.format(links=links)]
    for s in sections:
        title, intro = SECTIONS[s['name']]
        out += [f'## {title}', '']
        text = ' '.join(filter(None, [intro, ' '.join(s['intro'])]))
        if text:
            out += [text, '']
        out += [f'These settings are in the `[{s["name"]}]` section of `config.toml`.', '',
                '| Setting | Default | Restart | Description |', '|---|---|---|---|']
        for st in s['settings']:
            default = 'Set in Alpaca Pilot' if st['key'] in REDACTED else cell(show_default(st['default']))
            out.append(f'| `{st["key"]}` | {default} | {"Yes" if st["key"] in restart else ""} | {cell(st["description"])} |')
        out.append('')
    return '\n'.join(out)


def main() -> None:
    text = render()
    if '--check' in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding='utf-8') != text:
            print(f'{OUT.relative_to(ROOT)} is out of date with driver/config.toml; run utility/docs/make_config_reference.py')
            sys.exit(1)
        return
    OUT.write_text(text, encoding='utf-8')
    print(f'Wrote {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
