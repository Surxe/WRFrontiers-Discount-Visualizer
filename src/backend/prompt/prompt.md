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

1. Read `scraped_news_page.txt` and extract the date range for the current discount week.
2. Identify all discounted items mentioned in the **most recent** "Featured Items" section (the first one listed in the article).
3. For each discounted item name found, find the best match in `game_data.json` by comparing the item name to the `name` field.
4. Output the date range and the matched results (in the **exact order** they appear in the news article).

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

- Only include items from the **most recent** (first) "Featured Items" section.
- Do not include any item you cannot confidently match to an entry in `game_data.json`.
- Do not include discount values or prices.
- Format the date range string clearly, filling in missing month names. For example:
  - "May 26-June 2" -> "May 26 - June 2"
  - "May 19-26" -> "May 19 - May 26"
  - "May 5 - 12" -> "May 5 - May 12"
- Do not add any extra fields or structure to the output JSON.
- Output ONLY the raw JSON object string. Do not wrap in markdown code blocks. Do not add conversational text.
