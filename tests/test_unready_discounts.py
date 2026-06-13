import json
import os
import glob

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    module_json_path = os.path.join(root_dir, 'WRFrontiersDB-Data', 'current', 'Objects', 'Module.json')
    discounts_dir = os.path.join(root_dir, 'archive', 'discounts')

    # Load Module.json
    try:
        with open(module_json_path, 'r', encoding='utf-8') as f:
            modules_data = json.load(f)
    except Exception as e:
        print(f"Error loading {module_json_path}: {e}")
        return

    unready_modules = set()
    total_discounts_checked = 0

    # Comb through all discount files
    discount_files = glob.glob(os.path.join(discounts_dir, '*.json'))
    for file_path in discount_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                discount_data = json.load(f)
                items = discount_data.get('items', [])
                for item_id in items:
                    total_discounts_checked += 1
                    module = modules_data.get(item_id)
                    if module:
                        status = module.get('production_status')
                        if status != 'Ready':
                            unready_modules.add((item_id, status))
                    else:
                        unready_modules.add((item_id, 'Not Found in DB'))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Checked {total_discounts_checked} discount entries.")
    print("Modules discounted but NOT 'Ready':")
    if not unready_modules:
        print("  None found!")
    else:
        for module_id, status in sorted(unready_modules):
            print(f"  - {module_id} (Status: {status})")

if __name__ == '__main__':
    main()
