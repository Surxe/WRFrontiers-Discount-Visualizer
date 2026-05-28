# Discount Item Mapping Prompt

## Your Task

You are a game data analyst for War Robots: Frontiers. Your job is to read a news article about a discount event and identify which game modules are on discount, then map them to their official game data.

## Input Files (Read Only)

You have access to the following files in the `prompt/` directory:

- **`scraped_news_page.txt`**: The text content of a War Robots: Frontiers news article describing the current discount event. The article lists discounted items under sections like "War Robot Modules", "Weapons", and "Gear".
- **`game_data.json`**: A JSON array of all production-ready game modules. Each entry has:
  - `id`: The internal module ID string
  - `name`: The English display name of the module
  - `image_path`: The relative path to the module's icon image (within the `textures/` folder of the data repo)

## Your Goal

1. Read `scraped_news_page.txt` and identify all discounted items mentioned in the **most recent** "Featured Items" section (the first one listed in the article).
2. For each discounted item name found, find the best match in `game_data.json` by comparing the item name to the `name` field.
3. Output the matched results in the **exact order** they appear in the news article (Robots first, then Weapons, then Gear).

## Output

Output the matched results exclusively as a raw, valid JSON list of module ID strings to stdout. Do not output markdown code blocks (e.g. do not wrap in ```json ... ```), do not add any markdown formatting, and do not add any explanation or preamble text.

The output must be exactly in this format:
[
  "DA_Module_Robot_Example.1",
  "DA_Module_Robot_Example2.2"
]

## Rules

- Only include items from the **most recent** (first) "Featured Items" section.
- Do not include any item you cannot confidently match to an entry in `game_data.json`.
- Do not include discount values or prices.
- Do not add any extra fields or structure to the output list.
- Output ONLY the raw JSON string array. Do not wrap in markdown code blocks. Do not add conversational text.
