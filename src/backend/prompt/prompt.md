# Discount Item Mapping Prompt

## Your Task

You are a game data analyst for War Robots: Frontiers. Your job is to read a news article about a discount event, identify the discount week dates and discounted game modules, then map those modules to their official game data.

## Input Files (Read Only)

You have access to these files in the `prompt/` directory:

- **`scraped_news_page.txt`**: The text content of a War Robots: Frontiers news article. It lists discounted items under sections like "War Robots", "Weapons", and "Gear", and states the discount week date range.
- **`item_names.txt`**: An alternate input mode that contains only a list of item names, either comma-separated or one per line. When this file is present, do not expect any scraped article text or HTML content.
- **`game_data.json`**: A JSON array of all production-ready game modules. Each entry has:
  - `ref`: The internal object reference string
  - `name`: The English display name of the object

## Your Goal

1. If `item_names.txt` is present, read the list of item names from that file and ignore `scraped_news_page.txt`. Otherwise, read `scraped_news_page.txt` and identify the Featured Items section to map.
   - If a target date range is specified in your instructions, locate the "Featured Items" section that matches this target, supporting minor variations in spacing, dashes, and month names.
   - If no target date range is specified, find the latest/most recent "Featured Items" section, which is the first one listed in the article.
2. Extract the section's date range and standardize it into structured date fields.
3. Identify all discounted items mentioned in that section under "War Robot Modules", "Weapons", and "Gear".
4. For each discounted item name found, find the best match in `game_data.json` by comparing the item name to the `name` field.
5. Output the structured week date and matched results in the exact order they appear in the news article or the provided item list.

## Output

Output the results exclusively as a raw, valid JSON object to stdout. Do not output markdown code blocks, markdown formatting, explanations, or preamble text.

The output must be exactly in this format:

{
  "week": {
    "start_month": "May",
    "start_day": 26,
    "end_month": "June",
    "end_day": 2
  },
  "items": [
    "OBJID_VirtualBot::varangian",
    "OBJID_Module::DA_Module_Weapon_Zeus.0"
  ]
}

## Rules

- Do not include any item you cannot confidently match to an entry in `game_data.json`.
- Do not include discount values or prices.
- Output only `week` and `items`; do not add extra fields.
- **Date Normalization**:
  - Output date fields in the `week` object, not a date range string.
  - Use full month names (e.g., "January", "February", etc.).
  - Do not output `start_year` or `end_year` - these will be computed at runtime.
  - Fill in the end month from the start month if the end month is not explicitly written.
  - Examples:
    - `May 26 - June 2` -> `start_month: "May"`, `start_day: 26`, `end_month: "June"`, `end_day: 2`
    - `May 19 - 26` -> `start_month: "May"`, `start_day: 19`, `end_month: "May"`, `end_day: 26`
    - `June 2 - 9` -> `start_month: "June"`, `start_day: 2`, `end_month: "June"`, `end_day: 9`
    - `December 30 - January 6` -> `start_month: "December"`, `start_day: 30`, `end_month: "January"`, `end_day: 6`
- Output only the raw JSON object string. Do not wrap it in a markdown code block.
