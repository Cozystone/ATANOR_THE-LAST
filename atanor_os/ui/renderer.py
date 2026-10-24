"""Trusted renderer for the view body (charter §6): validates a declarative spec, computes what each
panel shows from the real files (pure `layout`), and draws it with tkinter (stdlib). Buttons are bound
only to allowed action ids. Rendering runs in its own process (`watch`) so thinking never blocks the
screen; the agent only ever writes `view.json`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ..world.fs_world import Workspace, name_ext
from ..world.view_world import EXTS, GROUPS, KEYS, PANELS

ALLOWED_ACTIONS = ('close',)              # buttons may only trigger these tools (gated by capability at execution)


def validate(spec):
    if type(spec) is not dict:
        raise ValueError('spec must be an object')
    for p, s in spec.items():
        if p not in PANELS:
            raise ValueError(f'unknown panel id {p!r}')
        if set(s) != {'kind', 'filter', 'sort', 'group'} or s['kind'] not in ('panel', 'compare'):
            raise ValueError(f'bad panel {p}: {s}')
        if s['filter'] not in EXTS or s['sort'] not in KEYS or s['group'] not in GROUPS:
            raise ValueError(f'bad binding in {p}: {s}')
    return spec


def _items(data, ext, key, group):
    files = [f for f in data.existing() if data.kind(f) == 'file']
    if ext != 'all':
        files = [f for f in files if name_ext(f) == ext]
    sizer = {'name': lambda f: f, 'ext': lambda f: (name_ext(f), f), 'size': lambda f: (data.path(f).stat().st_size, f)}
    files.sort(key=sizer[key])
    if group == 'ext':
        out, seen = [], []
        for f in files:
            e = name_ext(f)
            if e not in seen:
                seen.append(e)
                out.append(f'[{e}]')
            out.append(f'  {f}')
        return out
    return files


def layout(spec, data):
    """Pure: panel id -> {'title', 'items'} as the screen must show them."""
    validate(spec)
    out = {}
    for p, s in spec.items():
        title = f"{p} · {s['kind']} · filter={s['filter']} · sort={s['sort']} · group={s['group']}"
        if s['kind'] == 'compare':
            left = _items(data, s['filter'], s['sort'], 'none')
            right = _items(data, 'all', s['sort'], 'none')
            items = [f'L {x}' for x in left] + ['——'] + [f'R {x}' for x in right]
        else:
            items = _items(data, s['filter'], s['sort'], s['group'])
        out[p] = {'title': title, 'items': items}
    return out


def render_once(spec, data, root=None):
    """Draw the spec into a Tk root (created hidden when not given). Returns the widget map so a test can
    verify that what is drawn equals `layout` and that every button is bound to an allowed action id."""
    import tkinter as tk
    own = root is None
    if own:
        root = tk.Tk()
        root.withdraw()
    for w in list(root.winfo_children()):
        w.destroy()
    widgets = {'buttons': {}, 'lists': {}, 'root': root}
    lay = layout(spec, data)
    for col, (p, view) in enumerate(sorted(lay.items())):
        frame = tk.Frame(root, bd=1, relief='groove')
        frame.grid(row=0, column=col, sticky='nsew', padx=4, pady=4)
        tk.Label(frame, text=view['title']).pack()
        lb = tk.Listbox(frame, width=34, height=12)
        for it in view['items']:
            lb.insert('end', it)
        lb.pack()
        action = ('close', (p,))
        btn = tk.Button(frame, text=f'close {p}', command=lambda a=action: widgets.setdefault('requested', []).append(a))
        btn.pack()
        widgets['buttons'][p] = (btn, action)
        widgets['lists'][p] = lb
    root.update_idletasks()
    return widgets


def watch(spec_path, data_root, interval=0.25):
    """Standalone renderer process: redraw whenever view.json changes (decoupled from the agent)."""
    import tkinter as tk
    spec_path, data = Path(spec_path), Workspace(data_root, create=False)
    root = tk.Tk()
    root.title('ATANOR view')
    last = None

    def tick():
        nonlocal last
        try:
            m = spec_path.stat().st_mtime_ns
            if m != last:
                last = m
                render_once(json.loads(spec_path.read_text(encoding='utf-8')), data, root)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            root.title(f'ATANOR view — spec rejected: {e}')
        root.after(int(interval * 1000), tick)
    tick()
    root.mainloop()


if __name__ == '__main__':
    watch(sys.argv[1], sys.argv[2])
