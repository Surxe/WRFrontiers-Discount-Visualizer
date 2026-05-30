# Discount Item Mapping Prompt

## Your Task

You are a game data analyst for War Robots: Frontiers. Your job is to read a news article about a discount event and identify the date range for the discount week as well as which game modules are on discount, then map them to their official game data.

## Input Files (Read Only)

You have access to the following files in the `prompt/` directory:

- **`scraped_news_page.txt`**: The text content of a War Robots: Frontiers news article describing the current discount event. The article lists discounted items under sections like "War Robots", "Weapons", and "Gear". It also states the date range of the discount week (e.g. "May 26 - June 2").
- **`game_data.json`**: A JSON array of all production-ready game modules. Each entry has:
  - `ref`: The internal object reference string
  - `name`: The English display name of the object

## Your Goal

1. Read `scraped_news_page.txt` and identify the Featured Items section to map.
   - If a target date range is specified in your instructions (e.g. from the system or command line prompt), locate the "Featured Items" section that matches this target (supporting minor variations in spacing, dashes, and month names).
   - If no target date range is specified, find the latest/most recent "Featured Items" section (the first one listed in the article).
2. Extract the date range of that section and standardize it.
3. Identify all discounted items mentioned in that section (under "War Robot Modules", "Weapons", and "Gear").
4. For each discounted item name found, find the best match in `game_data.json` by comparing the item name to the `name` field.
5. Output the standardized date range and the matched results (in the **exact order** they appear in the news article).

## Output

Output the results exclusively as a raw, valid JSON object to stdout. Do not output markdown code blocks (e.g. do not wrap in ```json ... ```), do not add any markdown formatting, and do not add any explanation or preamble text.

The output must be exactly in this format:
{
  "date_range": "May 26 - June 2",
  "items": [
    "OBJID_VirtualBot::varangian",
    "OBJID_Module::DA_Module_Weapon_Zeus.0"
  ]
}

## Rules

- Do not include any item you cannot confidently match to an entry in `game_data.json`.
- Do not include discount values or prices.
- **Date Range Normalization**: You must output the date range exactly in the format `"Month Day - Month Day"`. 
  - Standardize dashes to space-surrounded hyphens: ` - `
  - Ensure month names are fully filled in for both the start and end date if they are not explicitly written. Examples:
    - "May 26–June 2" (using en-dash) -> "May 26 - June 2"
    - "May 19–26" -> "May 19 - May 26"
    - "May 5–12" -> "May 5 - May 12"
    - "June 2–9" -> "June 2 - June 9"
    - "April 28 – May 5" -> "April 28 - May 5"
- Do not add any extra fields or structure to the output JSON.
- Output ONLY the raw JSON object string. Do not wrap in markdown code blocks. Do not add conversational text.

