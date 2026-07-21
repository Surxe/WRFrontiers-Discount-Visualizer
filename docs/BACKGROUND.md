# War Robots: Frontiers — Background

This document describes the in-game mechanics that this project tracks and visualizes. It is a reference for understanding the data model and why the code does what it does.

---

## Modules

Modules are the core equipment system in War Robots: Frontiers. Every mech (called a **Virtual Bot** in the data) is assembled from individual modules that define how it looks, moves, and fights. There are five module categories:

| Category | Role |
|----------|------|
| **Chassis** | Defines mobility, weight capacity, and energy supply |
| **Torso** | Provides a signature core-gear ability and additional weapon slots |
| **Shoulder** | Adds weapon slots and carries shield generators |
| **Weapons** | Offensive modules; can be light (any slot) or heavy (universal slots only) |
| **Supply Gear** | Tactical consumable abilities usable a limited number of times per battle |
| **Cycle Gear** | Consumables abilities that must be charged by completing certain actions in game to get cycle points, such as doing damage or getting kills |

Each module has a **rarity** (Common, Uncommon, Rare, Epic) that affects its upgrade costs. The rarity is stored in `module_rarity_ref` on the `Module` object and resolves through `ModuleRarity` → `Rarity`.

Modules have a `production_status` field; only those marked `"Ready"` are included in game-data extraction (step 1 of the pipeline).

---

## Virtual Bots (Mechs)

A **Virtual Bot** represents a named mech preset — e.g. *Anansi*, *Ares*, *Alpha*. It carries a list of `core_module_refs` pointing to the specific Chassis, Torso, and Shoulder modules that make up that mech.

- **Mechs** (`character_type: "Mech"`) have 3 core modules: Chassis, Torso, and one Shoulder.
- **Titans** (`character_type: "Titan"`) have additional modules including distinct left/right Shoulders and titan-specific weapons.

When a discount is announced using a mech name (e.g. "Anansi"), the pipeline **expands** it into its individual core modules. Titan weapons are filtered out during this expansion — only the structural parts (Chassis, Torso, Shoulder) are shown in the discount grid.

At build time the frontend enforces that all three core modules of a mech share the same rarity; a mismatch intentionally fails the build.

---

## Weekly Discounts

Each week the game announces a curated set of discounted items. These are published externally (e.g. community channels) as plain English names. This project maps those names to specific module IDs and renders them as a visual grid.

A discount week is identified by a **date-range slug** (e.g. `06-16_06-23`). Each week produces:
- An archive entry under `archive/discounts/discounts_<slug>.json`
- A frontend grid layout at `src/frontend/public/data/week_grids/grid_<slug>.json`
- An entry in `weeks.json` and `discount_data.json`

The discount applies a reduced upgrade cost to each listed module for the duration of that week (see Salvage and Intel costs below).

---

## Salvage (Upgrade Currency)

**Salvage** (internal name: `Alloys`) is the primary crafting and upgrade currency. The in-game description: *"Cogs, nuts, bolts, and everything in between. Collect Salvage by scrapping modules. Use Salvage to build and upgrade your gear."*

Sources:
- Scrapping (disassembling) unwanted modules
- Daily Deals purchases
- Converting from Warp Reals (premium currency)

Salvage costs for upgrading a module scale with both **level** and **rarity**. Most upgrade levels cost only Salvage; certain levels (3, 5, 9, 13, …) cost only Intel instead. Level 1 is the crafting cost and is not discountable.

During a discount week the Salvage cost for a module's upgrade levels is reduced (roughly 50% for Common modules at most levels). The `RarityUpgradeCost` object stores both `standard` and `discounted` amounts per level per rarity. Epic modules currently have `discounted: null` at all levels, indicating they are not discounted.

Scrapping a module at a given level **refunds** a portion of the Salvage (and sometimes Intel) spent — tracked via `ScrapReward` objects linked from each module level.

---

## Intel (Upgrade Currency)

**Intel** is a secondary upgrade currency required at specific upgrade level thresholds. The in-game description: *"Trade secrets and knowledge learned on the job. Intel allows you to upgrade your equipment and improve your piloting skills faster."*

Sources:
- Completing Jobs (daily/weekly missions)

Intel gates progression at levels 3, 5, 9, and 13. Like Salvage, Intel costs also have a `discounted` value in `RarityUpgradeCost` for modules that are on a weekly discount — the reduction is more aggressive than Salvage (roughly 70% off for Common modules).

---

## Other Currencies

| Currency | Use |
|----------|-----|
| **Credits** | Hiring pilots, Daily Deals purchases; earned in battle and from jobs |
| **Warp Reals** | Premium currency; can be converted to Salvage or Credits |

---

## Module Upgrade Levels

All rarities have the same level range of 1 to 13. An item's level generally defines how strong it is, as many stats specific to the module group will scale. There are some stats that stay the same every level, albeit their game design technically supports the variance.

---

## Crafting / Constructor

Items can be acquired in two ways:
* Bought with Credits or Warp Realz in the Shop
* Crafted with salvage using their blueprints which are acquired as the player levels up their progression

When an item is acquired from the shop, it can start at any level, typically 1. When crafting, it always starts at level 1. It can be upgraded to a maximum of 13 using salvage and intel.