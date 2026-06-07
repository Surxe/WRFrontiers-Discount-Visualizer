import json
import subprocess
import os
import re
from pathlib import Path

# Load Module.json and VirtualBot.json to create name-to-OBJID mappings
MODULE_JSON_PATH = Path("WRFrontiersDB-Data/current/Objects/Module.json")
VIRTUAL_BOT_JSON_PATH = Path("WRFrontiersDB-Data/current/Objects/VirtualBot.json")

def load_name_mappings():
    """Create mappings from human-readable names to OBJID format."""
    module_name_to_id = {}
    bot_name_to_id = {}
    
    # Load Module.json
    with open(MODULE_JSON_PATH, 'r', encoding='utf-8') as f:
        modules_data = json.load(f)
    
    for module_id, module_data in modules_data.items():
        name_field = module_data.get("name", {})
        english_name = name_field.get("en", "")
        if english_name:
            # Store both the exact name and lowercase version for case-insensitive matching
            module_name_to_id[english_name] = f"OBJID_Module::{module_id}"
            module_name_to_id[english_name.lower()] = f"OBJID_Module::{module_id}"
    
    # Load VirtualBot.json
    with open(VIRTUAL_BOT_JSON_PATH, 'r', encoding='utf-8') as f:
        bots_data = json.load(f)
    
    for bot_id, bot_data in bots_data.items():
        name_field = bot_data.get("name", {})
        english_name = name_field.get("en", "")
        if english_name:
            bot_name_to_id[english_name] = f"OBJID_VirtualBot::{bot_id}"
            bot_name_to_id[english_name.lower()] = f"OBJID_VirtualBot::{bot_id}"
    
    return module_name_to_id, bot_name_to_id

def parse_old_discounts_md(file_path):
    """Parse the archive/old_discounts.md file to extract weeks and items."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    weeks = []
    current_week = None
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip the note line
        if line.startswith("NOTE TO USER:") or line.startswith("March 24 to present"):
            continue
        
        # Check if this is a date range line (e.g., "March 17-24" or "March 3-10:")
        # Match lines that start with a month name followed by a number
        date_match = re.match(r'^([A-Za-z]+\s+\d+)', line)
        if date_match and not line.startswith("Robots:") and not line.startswith("Weapons:") and not line.startswith("Gear:"):
            # Save previous week if exists
            if current_week:
                weeks.append(current_week)
            
            # Start new week
            date_range = line.rstrip(':').strip()
            # Normalize date range format - only replace dashes/ens/to that are between numbers
            # This prevents splitting month names like "August" or "September"
            date_range = re.sub(r'(\d+)\s*[-–to]+\s*(\d+)', r'\1 - \2', date_range)
            current_week = {
                "date_range": date_range,
                "items": []
            }
        elif current_week:
            # Parse items line
            if line.startswith("Robots:"):
                items = [item.strip() for item in line.replace("Robots:", "").split(',')]
                for item in items:
                    if item:
                        current_week["items"].append(("robot", item))
            elif line.startswith("Weapons:"):
                items = [item.strip() for item in line.replace("Weapons:", "").split(',')]
                for item in items:
                    if item:
                        current_week["items"].append(("weapon", item))
            elif line.startswith("Gear:"):
                items = [item.strip() for item in line.replace("Gear:", "").split(',')]
                for item in items:
                    if item:
                        # Remove parenthetical notes like "(Supply Gear)"
                        clean_item = re.sub(r'\s*\([^)]*\)', '', item).strip()
                        current_week["items"].append(("gear", clean_item))
            elif line.startswith("War Robot Modules:"):
                items = [item.strip() for item in line.replace("War Robot Modules:", "").split(',')]
                for item in items:
                    if item:
                        current_week["items"].append(("robot", item))
    
    # Add the last week
    if current_week:
        weeks.append(current_week)
    
    return weeks

def convert_names_to_objids(weeks, module_name_to_id, bot_name_to_id):
    """Convert human-readable names to OBJID format."""
    converted_weeks = []
    
    for week in weeks:
        objid_items = []
        unmatched_items = []
        
        for item_type, item_name in week["items"]:
            # Try to match as bot first
            if item_name.lower() in bot_name_to_id:
                objid_items.append(bot_name_to_id[item_name.lower()])
            # Then try as module
            elif item_name.lower() in module_name_to_id:
                objid_items.append(module_name_to_id[item_name.lower()])
            else:
                unmatched_items.append((item_type, item_name))
        
        if unmatched_items:
            print(f"  [!] Unmatched items for {week['date_range']}:")
            for item_type, item_name in unmatched_items:
                print(f"      - {item_type}: {item_name}")
        
        if objid_items:
            converted_weeks.append({
                "date_range": week["date_range"],
                "items": objid_items
            })
    
    return converted_weeks

def main():
    print("Loading name mappings from Module.json and VirtualBot.json...")
    module_name_to_id, bot_name_to_id = load_name_mappings()
    print(f"  -> Loaded {len(module_name_to_id)} module names")
    print(f"  -> Loaded {len(bot_name_to_id)} bot names")
    
    print("\nParsing archive/old_discounts.md...")
    weeks = parse_old_discounts_md("archive/old_discounts.md")
    print(f"  -> Found {len(weeks)} weeks")
    
    print("\nConverting human-readable names to OBJID format...")
    converted_weeks = convert_names_to_objids(weeks, module_name_to_id, bot_name_to_id)
    print(f"  -> Converted {len(converted_weeks)} weeks")
    
    # Output directory for step4 input
    output_file = "src/backend/prompt/output/discounts.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    print(f"\nProcessing weeks through step4...")
    for i, week in enumerate(converted_weeks, 1):
        print(f"\n[{i}/{len(converted_weeks)}] Processing: {week['date_range']}")
        
        # Write to step4 input
        with open(output_file, "w") as f:
            json.dump(week, f, indent=2)
        
        # Run step4
        try:
            subprocess.run(["python", "src/backend/step4_read_output.py"], check=True)
            print(f"  -> Successfully processed {week['date_range']}")
        except subprocess.CalledProcessError as e:
            print(f"  -> ERROR processing {week['date_range']}: {e}")
    
    print(f"\nCompleted! Processed {len(converted_weeks)} weeks.")
    print(f"Output files are in archive/discounts/")

if __name__ == "__main__":
    main()
