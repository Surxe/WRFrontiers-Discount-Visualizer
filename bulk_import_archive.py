import json
import subprocess
import os
import re
from pathlib import Path
from datetime import datetime

# Load Module.json and VirtualBot.json to create name-to-OBJID mappings
MODULE_JSON_PATH = Path("WRFrontiersDB-Data/current/Objects/Module.json")
VIRTUAL_BOT_JSON_PATH = Path("WRFrontiersDB-Data/current/Objects/VirtualBot.json")

# Month abbreviation mapping
MONTH_ABBR = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec"
}

def standardize_date_format(date_range):
    """Standardize date format to use abbreviated months and consistent format."""
    # Replace full month names with abbreviations
    for full_month, abbr in MONTH_ABBR.items():
        date_range = date_range.replace(full_month, abbr)
    
    # Remove "th", "st", "nd", "rd" suffixes from dates
    date_range = re.sub(r'(\d+)(th|st|nd|rd)', r'\1', date_range)
    
    # Normalize to format: "MMM DD, YYYY - MMM DD, YYYY"
    # First, try to parse and reconstruct
    parts = date_range.split('-')
    if len(parts) == 2:
        start_part = parts[0].strip()
        end_part = parts[1].strip()
        
        # Extract year from end part if present
        year = ""
        year_match = re.search(r',\s*(\d{4})', end_part)
        if year_match:
            year = year_match.group(1)
            # Remove year but keep the rest of the end part
            end_part = end_part[:year_match.start()].strip()
        
        # Extract year from start part if present
        start_year = ""
        start_year_match = re.search(r',\s*(\d{4})', start_part)
        if start_year_match:
            start_year = start_year_match.group(1)
            # Remove year but keep the rest of the start part
            start_part = start_part[:start_year_match.start()].strip()
        
        # Extract month from start part
        start_month_match = re.match(r'^([A-Za-z]+)', start_part)
        start_month = start_month_match.group(1) if start_month_match else ""
        
        # If end part is just a number (no month), add the month from start
        if re.match(r'^\d+$', end_part) and start_month:
            end_part = f"{start_month} {end_part}"
        
        # Use the year from start part if end part doesn't have one
        if not year and start_year:
            year = start_year
        # Use the year from end part if start part doesn't have one
        elif year and not start_year:
            start_year = year
        
        # Default to 2026 if no year found
        if not year:
            year = "2026"
        if not start_year:
            start_year = year
        
        # Reconstruct with year on both dates
        date_range = f"{start_part}, {start_year} - {end_part}, {year}"
    
    return date_range

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
            # Standardize date format with abbreviated months
            date_range = standardize_date_format(date_range)
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

def parse_date_for_sorting(date_range):
    """Parse a date range string into a sortable tuple (year, month, day)."""
    # Extract the first date from the range
    # Format examples: "Jan 6, 2026 - Jan 13, 2026" or "Dec 30, 2026 - Jan 6, 2026"
    match = re.match(r'([A-Za-z]+)\s+(\d+),?\s*(\d{4})?', date_range)
    if match:
        month_str = match.group(1)
        day = int(match.group(2))
        year_str = match.group(3)
        
        # Default to 2026 if year not specified
        year = int(year_str) if year_str else 2026
        
        # Map abbreviated month to number
        month_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
        }
        month = month_map.get(month_str, 1)
        
        return (year, month, day)
    
    return (9999, 12, 31)  # Default to end of time if parsing fails

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
    
    # Sort weeks chronologically
    weeks.sort(key=lambda w: parse_date_for_sorting(w["date_range"]))
    print(f"  -> Sorted weeks chronologically")
    
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
