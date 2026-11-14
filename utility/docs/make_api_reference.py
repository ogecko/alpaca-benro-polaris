"""
Generate the device API references in docs/ from the driver's Alpaca endpoint classes.

Each endpoint is a class in driver/rotator.py (or telescope.py) named after its ASCOM member, with
on_get and/or on_put responders. The page lists each one with its methods, the request fields it
reads (from get_request_field calls), whether it's implemented, and the class's docstring, so the
docstrings are the place to describe what an endpoint does.

Usage (from the repo root):
    python utility/docs/make_api_reference.py           # write the pages
    python utility/docs/make_api_reference.py --check   # exit 1 if a page is out of date
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Members every ASCOM device has, listed separately from the device's own
COMMON = {'action', 'commandblind', 'commandbool', 'commandstring', 'connected', 'description',
          'driverinfo', 'driverversion', 'interfaceversion', 'name', 'supportedactions'}

DEVICES = [
    {
        'module': ROOT / 'driver' / 'rotator.py',
        'page': ROOT / 'docs' / 'rotator-api.md',
        'device': 'rotator',
        'title': 'Rotator API Reference',
        'intro': (
            "The Rotator rotates the camera around the direction it's pointing, while the mount stays on target. "
            "It implements the ASCOM **IRotatorV3** interface: see the [ASCOM Rotator interface](https://ascom-standards.org/newdocs/rotator.html) "
            "for the standard behaviour of each member. Its `position` is the camera's Position Angle on the sky, and its `mechanicalposition` "
            "is the camera's Roll Angle relative to the horizon (see [Roll Angle vs Position Angle](./control.md#roll-angle-vs-position-angle)). "
            "So `moveabsolute` to 0 turns the top of the frame to celestial north, not level with the horizon: use `movemechanical` to set the Roll Angle."
        ),
    },
    {
        'module': ROOT / 'driver' / 'telescope.py',
        'page': ROOT / 'docs' / 'telescope-api.md',
        'device': 'telescope',
        'title': 'Telescope API Reference',
        'intro': (
            "The Telescope points and tracks the mount. "
            "It implements the ASCOM **ITelescopeV3** interface: see the [ASCOM Telescope interface](https://ascom-standards.org/newdocs/telescope.html) "
            "for the standard behaviour of each member. It's an Alt/Az mount (`alignmentmode` 0), and its right ascension and declination are "
            "topocentric JNow, the equinox of date (`equatorialsystem` 1). For J2000 coordinates, use the `Polaris:J2000Goto` and `Polaris:J2000Sync` "
            "[Device Actions](./alpaca-api.md#device-actions). The driver keeps every slew within what the Polaris can physically reach, "
            "where Altitude and Roll limit each other (see [Reachable Envelope](./kinematics.md#reachable-envelope))."
        ),
    },
]

HEADER = '''# {title}
[{device_title} Members](#{device}-members) · [Common Members](#common-members)

{intro}

Each member is at `http://<driver address>:5555/api/v1/{device}/0/<member>`. GET requests read a property; PUT requests change it or run a method, with the fields listed as form data. Every request also needs `ClientID` and `ClientTransactionID`; see the [Alpaca API Reference](./alpaca-api.md) for examples.

This page is generated from the driver's code (`{module}`) by `utility/docs/make_api_reference.py`: change the endpoint classes' docstrings rather than this page.
'''


def request_fields(node: ast.AST) -> list[str]:
    """The request fields an endpoint reads, in order, apart from ClientID."""
    fields = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'get_request_field' and n.args:
            arg = n.args[0]
            if isinstance(arg, ast.Constant) and arg.value != 'ClientID' and arg.value not in fields:
                fields.append(arg.value)
    return fields


def not_implemented(methods: list[ast.AsyncFunctionDef]) -> bool:
    """True when every responder only returns NotImplementedException."""
    def only_not_impl(fn):
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        return 'NotImplementedException' in names and len(fn.body) == 1
    return all(only_not_impl(m) for m in methods)


def endpoints(module: Path) -> list[dict]:
    out = {}   # by name: a class defined twice is the later one, as in Python
    for node in ast.parse(module.read_text(encoding='utf-8')).body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [m for m in node.body if isinstance(m, ast.AsyncFunctionDef) and m.name in ('on_get', 'on_put')]
        if not methods:
            continue
        out[node.name] = {
            'name': node.name,
            'methods': ' / '.join(m.name[3:].upper() for m in methods),
            'fields': request_fields(node),
            'missing': not_implemented(methods),
            'doc': ' '.join((ast.get_docstring(node) or '').split()),
        }
    return list(out.values())


def table(rows: list[dict]) -> list[str]:
    lines = ['| Member | Method | Fields | Description |', '|---|---|---|---|']
    for r in sorted(rows, key=lambda r: r['name']):
        fields = ', '.join(f'`{f}`' for f in r['fields']) or ''
        doc = r['doc'] + (' *(Not implemented.)*' if r['missing'] and 'Not implemented' not in r['doc'] else '')
        lines.append(f"| `{r['name']}` | {r['methods']} | {fields} | {doc.replace('|', chr(92) + '|')} |")
    return lines


def render(d: dict) -> str:
    rows = endpoints(d['module'])
    device_title = d['device'].capitalize()
    out = [HEADER.format(title=d['title'], device=d['device'], device_title=device_title, intro=d['intro'],
                         module=d['module'].relative_to(ROOT).as_posix())]
    out += [f'## {device_title} Members', ''] + table([r for r in rows if r['name'] not in COMMON]) + ['']
    out += ['## Common Members', '', 'The members every ASCOM device has.', ''] + table([r for r in rows if r['name'] in COMMON]) + ['']
    return '\n'.join(out)


def main() -> None:
    stale = []
    for d in DEVICES:
        text = render(d)
        if '--check' in sys.argv:
            if not d['page'].exists() or d['page'].read_text(encoding='utf-8') != text:
                stale.append(d['page'])
        else:
            d['page'].write_text(text, encoding='utf-8')
            print(f"Wrote {d['page'].relative_to(ROOT)}")
    if stale:
        for p in stale:
            print(f'{p.relative_to(ROOT)} is out of date with the driver; run utility/docs/make_api_reference.py')
        sys.exit(1)


if __name__ == '__main__':
    main()
