import json, sys
from pathlib import Path

sys.path.insert(0, 'src/backend')
import grid_generator
from config import date_range_to_slug

ARCHIVE_DIR = Path('archive/discounts')
WEEK_GRIDS_DIR = Path('src/frontend/public/data/week_grids')
DATA_REPO = Path('WRFrontiersDB-Data/current/Objects')

# Regenerates the src/frontend/public/data/grid_weeks/* files off of the archive/discounts/* files by passing them through grid_generator.build_grid()
# Why? Used when grid_generator.py changes (primarily bug fixes) to re-generate the non-current grid files with the new logic retroactively

modules_data = json.load(open(DATA_REPO / 'Module.json', encoding='utf-8'))
module_types_data = json.load(open(DATA_REPO / 'ModuleType.json', encoding='utf-8'))
virtual_bots_data = json.load(open(DATA_REPO / 'VirtualBot.json', encoding='utf-8'))
presets_data = json.load(open(DATA_REPO / 'CharacterPreset.json', encoding='utf-8'))

for f in sorted(ARCHIVE_DIR.glob('discounts_*.json')):
    data = json.load(open(f, encoding='utf-8'))
    date_range = data['date_range']
    module_ids = [item['id'] for item in data['items'] if item.get('id')]
    grid_data = grid_generator.build_grid(module_ids, modules_data, module_types_data, virtual_bots_data, presets_data)
    slug = date_range_to_slug(date_range)
    out = WEEK_GRIDS_DIR / f'grid_{slug}.json'
    json.dump(grid_data, open(out, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    std = len(grid_data.get('standardRows', []))
    titan = len(grid_data.get('titanRows', []))
    print(f'{slug}: {std} std rows, {titan} titan rows -> {out.name}')

print('Done.')
