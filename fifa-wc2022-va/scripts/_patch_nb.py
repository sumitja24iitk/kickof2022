import json

nb_path = 'notebooks/00_schema_exploration.ipynb'
with open(nb_path) as f:
    nb = json.load(f)

new_source = (
    'print("=== Pitch coordinate system ===")\n'
    'import numpy as np\n'
    'locs = events["location"].dropna()\n'
    'def extract_xy(v):\n'
    '    if isinstance(v, (list, np.ndarray)) and len(v) >= 2:\n'
    '        return float(v[0]), float(v[1])\n'
    '    return None, None\n'
    'xs = locs.apply(lambda v: extract_xy(v)[0]).dropna()\n'
    'ys = locs.apply(lambda v: extract_xy(v)[1]).dropna()\n'
    'print(f"x range: {xs.min():.1f} - {xs.max():.1f}")\n'
    'print(f"y range: {ys.min():.1f} - {ys.max():.1f}")\n'
    '\n'
    'shot_locs = events[events["type"] == "Shot"]["location"].dropna()\n'
    'shot_xs = shot_locs.apply(lambda v: extract_xy(v)[0]).dropna()\n'
    'print(f"\\nShot x range (should cluster near 120): {shot_xs.min():.1f} - {shot_xs.max():.1f}")\n'
    'print(f"Shot x median: {shot_xs.median():.1f}")'
)

for cell in nb['cells']:
    if cell.get('id', '').endswith('18'):
        cell['source'] = new_source
        cell['outputs'] = []
        print('Patched cell', cell['id'])
        break

with open(nb_path, 'w') as f:
    json.dump(nb, f, indent=1)
print('Saved.')
