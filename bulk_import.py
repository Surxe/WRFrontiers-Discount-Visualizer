import json
import subprocess
import os

WEEKS = [
    {
        "date_range": "May 19 - May 26",
        "items": [
            "OBJID_VirtualBot::heike", "OBJID_VirtualBot::orochi",
            "OBJID_Module::DA_Module_Weapon_Slugger.0", "OBJID_Module::DA_Module_Weapon_Thunder.0",
            "OBJID_Module::DA_Module_Weapon_Zeus.0", "OBJID_Module::DA_Module_Weapon_Gimcoil.0",
            "OBJID_Module::DA_Module_Ability_TensionLink.1", "OBJID_Module::DA_Module_Ability_Spotlight.1",
            "OBJID_Module::DA_Module_Ability_GhostTurret.1", "OBJID_Module::DA_Module_Ability_BlastWave.1"
        ]
    },
    {
        "date_range": "May 12 - May 19",
        "items": [
            "OBJID_VirtualBot::fenrir", "OBJID_VirtualBot::mesa", "OBJID_VirtualBot::purifier", "OBJID_VirtualBot::matriarch",
            "OBJID_Module::DA_Module_Weapon_Fowler.0", "OBJID_Module::DA_Module_Weapon_Incinerator.0",
            "OBJID_Module::DA_Module_Weapon_Locust.0", "OBJID_Module::DA_Module_Weapon_Hive.0",
            "OBJID_Module::DA_Module_Ability_AmmoGenerator.1", "OBJID_Module::DA_Module_Ability_CounterAttack.1",
            "OBJID_Module::DA_Module_Ability_FuelReserve.1", "OBJID_Module::DA_Module_Ability_Regeneration.1",
            "OBJID_Module::DA_Module_Ability_TensionLink.1"
        ]
    },
    {
        "date_range": "May 5 - May 12",
        "items": [
            "OBJID_VirtualBot::tyr", "OBJID_VirtualBot::fury", "OBJID_VirtualBot::siren", "OBJID_VirtualBot::alpha",
            "OBJID_Module::DA_Module_Weapon_Pulsar.0", "OBJID_Module::DA_Module_Weapon_Railgun.0",
            "OBJID_Module::DA_Module_Weapon_Trident.0", "OBJID_Module::DA_Module_Weapon_Vortex.0",
            "OBJID_Module::DA_Module_Weapon_Callisto.0",
            "OBJID_Module::DA_Module_Ability_BlockingField.1", "OBJID_Module::DA_Module_Ability_CounterAttack.1",
            "OBJID_Module::DA_Module_Ability_GhostTurret.1", "OBJID_Module::DA_Module_Ability_Homing.1",
            "OBJID_Module::DA_Module_Ability_SpeedBoost.1", "OBJID_Module::DA_Module_Ability_Umbrella.1"
        ]
    },
    {
        "date_range": "April 28 - May 5",
        "items": [
            "OBJID_VirtualBot::harpy", "OBJID_VirtualBot::typhon", "OBJID_VirtualBot::loki",
            "OBJID_Module::DA_Module_Weapon_Glory.0", "OBJID_Module::DA_Module_Weapon_Railgun.0",
            "OBJID_Module::DA_Module_Weapon_Shocktrain.0", "OBJID_Module::DA_Module_Weapon_Trebuchet.0",
            "OBJID_Module::DA_Module_Weapon_Skuld.0",
            "OBJID_Module::DA_Module_Ability_Dazzle.1", "OBJID_Module::DA_Module_Ability_FuelReserve.1",
            "OBJID_Module::DA_Module_Ability_GhostTurret.1", "OBJID_Module::DA_Module_Ability_Grounded.1",
            "OBJID_Module::DA_Module_Ability_Spotlight.1", "OBJID_Module::DA_Module_Ability_Umbrella.1"
        ]
    },
    {
        "date_range": "April 21 - April 28",
        "items": [
            "OBJID_VirtualBot::ravana", "OBJID_VirtualBot::anansi", "OBJID_VirtualBot::kumo",
            "OBJID_Module::DA_Module_Weapon_StickyGun.0", "OBJID_Module::DA_Module_Weapon_MLx2.0",
            "OBJID_Module::DA_Module_Weapon_Horde.0", "OBJID_Module::DA_Module_Weapon_Conflux.0",
            "OBJID_Module::DA_Module_Ability_SpeedBoost.1", "OBJID_Module::DA_Module_Ability_RegenerationFull.1",
            "OBJID_Module::DA_Module_Ability_Atrophy.1", "OBJID_Module::DA_Module_Ability_Dazzle.1",
            "OBJID_Module::DA_Module_Ability_TensionLink.1"
        ]
    },
    {
        "date_range": "April 14 - April 21",
        "items": [
            "OBJID_VirtualBot::bulwark", "OBJID_VirtualBot::crix", "OBJID_VirtualBot::ares",
            "OBJID_Module::DA_Module_Weapon_Thunder.0", "OBJID_Module::DA_Module_Weapon_Stormpike.0",
            "OBJID_Module::DA_Module_Weapon_Scourge.0",
            "OBJID_Module::DA_Module_Ability_SmokeWall.1", "OBJID_Module::DA_Module_Ability_RegenerationFull.1",
            "OBJID_Module::DA_Module_Ability_Grounded.1", "OBJID_Module::DA_Module_Ability_MineField.1",
            "OBJID_Module::DA_Module_Ability_Dazzle.1", "OBJID_Module::DA_Module_Ability_KineticPulse.1"
        ]
    },
    {
        "date_range": "April 7 - April 14",
        "items": [
            "OBJID_VirtualBot::griffin", "OBJID_VirtualBot::decker", "OBJID_VirtualBot::ceres",
            "OBJID_Module::DA_Module_Weapon_Buckshot.0", "OBJID_Module::DA_Module_Weapon_Hefty.0",
            "OBJID_Module::DA_Module_Weapon_Bisector.0", "OBJID_Module::DA_Module_Weapon_Zenit.0",
            "OBJID_Module::DA_Module_Ability_SmokeWall.1", "OBJID_Module::DA_Module_Ability_Umbrella.1",
            "OBJID_Module::DA_Module_Ability_ArmorShield.1", "OBJID_Module::DA_Module_Ability_SupplySurge.1",
            "OBJID_Module::DA_Module_Ability_GhostTurret.1", "OBJID_Module::DA_Module_Ability_CounterAttack.1"
        ]
    },
    {
        "date_range": "March 31 - April 7",
        "items": [
            "OBJID_VirtualBot::raven", "OBJID_VirtualBot::cyclops", "OBJID_VirtualBot::phantom",
            "OBJID_Module::DA_Module_Weapon_Gozer.0", "OBJID_Module::DA_Module_Weapon_Toxin.0",
            "OBJID_Module::DA_Module_Weapon_Twinflare.0",
            "OBJID_Module::DA_Module_Ability_BlastWave.1", "OBJID_Module::DA_Module_Ability_InfiniteAmmo.1",
            "OBJID_Module::DA_Module_Ability_MineField.1", "OBJID_Module::DA_Module_Ability_BlockingField.1",
            "OBJID_Module::DA_Module_Ability_DashBlinkedVisible.1", "OBJID_Module::DA_Module_Ability_Homing.1",
            "OBJID_Module::DA_Module_Ability_IronVeil.1"
        ]
    },
    {
        "date_range": "March 24 - March 31",
        "items": [
            "OBJID_VirtualBot::scorpion", "OBJID_VirtualBot::lancelot", "OBJID_VirtualBot::grim",
            "OBJID_Module::DA_Module_Weapon_Tusk.0", "OBJID_Module::DA_Module_Weapon_Punisher.0",
            "OBJID_Module::DA_Module_Weapon_Katzbalger.0", "OBJID_Module::DA_Module_Weapon_Jigsaw.0",
            "OBJID_Module::DA_Module_Ability_Repulsor.1", "OBJID_Module::DA_Module_Ability_TensionLink.1",
            "OBJID_Module::DA_Module_Ability_SpeedBoost.1", "OBJID_Module::DA_Module_Ability_CounterAttack.1"
        ]
    }
]

output_file = "src/backend/prompt/output/discounts.json"
os.makedirs(os.path.dirname(output_file), exist_ok=True)

for week in WEEKS:
    with open(output_file, "w") as f:
        json.dump(week, f, indent=2)
    print(f"Running step4 for {week['date_range']}...")
    subprocess.run(["python", "src/backend/step4_archive_gen_grid.py"], check=True)
