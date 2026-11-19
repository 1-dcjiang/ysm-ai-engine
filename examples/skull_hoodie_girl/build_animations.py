"""
YSM 2.6.0 Base Animation & Manifest Generator for Skull Hoodie Girl (skull_hoodie_girl).
Generates:
  - dist/skull_hoodie_girl/animations/main.animation.json (all 29 required YSM base states)
  - dist/skull_hoodie_girl/animations/arm.animation.json  (item-use arm poses)
  - dist/skull_hoodie_girl/ysm.json                       (YSM spec=2 manifest)
  - dist/skull_hoodie_girl/lang/{zh_cn,en_us}.json        (localization)

Rotation sign reminder (Bedrock / YSM):
  rx > 0 : bottom of limb/hair swings BACKWARD (+Z), head/torso pitches FORWARD (-Z)
  rx < 0 : bottom of limb/hair swings FORWARD (-Z), head/torso pitches BACKWARD (+Z)
  ry > 0 : turns front (-Z) toward character's RIGHT (-X)
  rz > 0 : tilts bottom outward to character's RIGHT (-X); rz < 0 tilts outward to LEFT (+X)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACK_DIR = ROOT / "out" / "skull_hoodie_girl"


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_main_animations() -> dict:
    """All 29 core YSM 2.6.0 base animations with gentle anti-clipping hair sway."""
    anims = {
        "empty": {
            "loop": True,
            "animation_length": 1.0,
            "bones": {},
        },
        "gui": {
            "loop": True,
            "animation_length": 2.4,
            "bones": {
                "Body": {
                    "rotation": ["math.sin(q.anim_time * 150) * 1.0", 0, 0],
                    "position": [0, "math.sin(q.anim_time * 150) * 0.12", 0],
                },
                "RightArm": {"rotation": ["math.sin(q.anim_time * 150 - 30) * 1.5", 0, 1.0]},
                "LeftArm": {"rotation": ["math.sin(q.anim_time * 150 - 30) * 1.5", 0, -1.0]},
                "HairBack": {"rotation": ["3.0 + math.sin(q.anim_time * 150 - 45) * 1.8", 0, 0]},
                "HairBackLower": {"rotation": ["2.5 + math.sin(q.anim_time * 150 - 90) * 2.2", 0, 0]},
                "HairFrontRight": {"rotation": [0, 0, "math.sin(q.anim_time * 150 - 30) * 1.0"]},
                "HairFrontLeft": {"rotation": [0, 0, "-math.sin(q.anim_time * 150 - 30) * 1.0"]},
            },
        },
        "idle": {
            "loop": True,
            "animation_length": 3.0,
            "bones": {
                "Body": {
                    "rotation": ["math.sin(q.anim_time * 120) * 1.1", 0, 0],
                    "position": [0, "math.sin(q.anim_time * 120) * 0.14", 0],
                },
                "AllHead": {
                    "rotation": ["math.sin(q.anim_time * 120 - 35) * 1.2", 0, "math.cos(q.anim_time * 60) * 0.8"],
                },
                "RightArm": {
                    "rotation": ["math.sin(q.anim_time * 120 - 25) * 1.8", 0, "1.2 + math.sin(q.anim_time * 120) * 0.8"],
                },
                "LeftArm": {
                    "rotation": ["math.sin(q.anim_time * 120 - 25) * 1.8", 0, "-1.2 - math.sin(q.anim_time * 120) * 0.8"],
                },
                "HairBack": {"rotation": ["3.2 + math.sin(q.anim_time * 120 - 45) * 1.8", 0, 0]},
                "HairBackLower": {"rotation": ["2.5 + math.sin(q.anim_time * 120 - 85) * 2.2", 0, 0]},
                "HairFrontRight": {"rotation": ["1.0 + math.sin(q.anim_time * 120 - 40) * 1.0", 0, 0.8]},
                "HairFrontLeft": {"rotation": ["1.0 + math.sin(q.anim_time * 120 - 40) * 1.0", 0, -0.8]},
            },
        },
        "walk": {
            "loop": True,
            "animation_length": 1.0,
            "bones": {
                "Waist": {
                    "position": [0, "math.abs(math.cos(q.anim_time * 360)) * 0.65 - 0.25", 0],
                    "rotation": [2.0, "math.sin(q.anim_time * 360) * 3.5", "math.sin(q.anim_time * 360) * 1.5"],
                },
                "Body": {"rotation": [2.5, "math.sin(q.anim_time * 360) * -2.0", 0]},
                "AllHead": {"rotation": [-2.5, 0, "math.sin(q.anim_time * 360) * -1.2"]},
                "RightLeg": {"rotation": ["math.sin(q.anim_time * 360) * 30", 0, 0]},
                "LeftLeg": {"rotation": ["math.sin(q.anim_time * 360) * -30", 0, 0]},
                "RightArm": {"rotation": ["math.sin(q.anim_time * 360) * -24", 0, 2.0]},
                "LeftArm": {"rotation": ["math.sin(q.anim_time * 360) * 24", 0, -2.0]},
                "Skirt": {"rotation": ["2.5 + math.abs(math.sin(q.anim_time * 360)) * 3.5", 0, 0]},
                # Positive rx swings back hair cleanly BACKWARD (+Z) away from legs/back!
                "HairBack": {"rotation": ["8.5 + math.abs(math.sin(q.anim_time * 360)) * 4.5", 0, "math.sin(q.anim_time * 360) * -2.2"]},
                "HairBackLower": {"rotation": ["6.5 + math.sin(q.anim_time * 720 - 40) * 3.5", 0, "math.sin(q.anim_time * 360 - 30) * -2.5"]},
                "HairFrontRight": {"rotation": ["2.5 + math.sin(q.anim_time * 360) * 2.5", 0, 1.5]},
                "HairFrontLeft": {"rotation": ["2.5 - math.sin(q.anim_time * 360) * 2.5", 0, -1.5]},
            },
        },
        "run": {
            "loop": True,
            "animation_length": 0.65,
            "bones": {
                "Waist": {
                    "position": [0, "math.abs(math.cos(q.anim_time * 553.8)) * 1.15 - 0.55", 0],
                    "rotation": [6.0, "math.sin(q.anim_time * 553.8) * 5.0", "math.sin(q.anim_time * 553.8) * 2.2"],
                },
                "Body": {"rotation": [7.5, "math.sin(q.anim_time * 553.8) * -3.5", 0]},
                "AllHead": {"rotation": [-10.0, 0, "math.sin(q.anim_time * 553.8) * -1.8"]},
                "RightLeg": {"rotation": ["math.sin(q.anim_time * 553.8) * 48", 0, 0]},
                "LeftLeg": {"rotation": ["math.sin(q.anim_time * 553.8) * -48", 0, 0]},
                "RightArm": {"rotation": ["math.sin(q.anim_time * 553.8) * -44", 0, 4.5]},
                "LeftArm": {"rotation": ["math.sin(q.anim_time * 553.8) * 44", 0, -4.5]},
                "Skirt": {"rotation": ["6.0 + math.abs(math.sin(q.anim_time * 553.8)) * 5.0", 0, 0]},
                "HairBack": {"rotation": ["18.0 + math.abs(math.sin(q.anim_time * 553.8)) * 6.5", 0, "math.sin(q.anim_time * 553.8) * -3.0"]},
                "HairBackLower": {"rotation": ["14.0 + math.sin(q.anim_time * 1107.7 - 50) * 5.0", 0, "math.sin(q.anim_time * 553.8 - 40) * -3.5"]},
                "HairFrontRight": {"rotation": ["5.5 + math.sin(q.anim_time * 553.8) * 4.0", 0, 3.0]},
                "HairFrontLeft": {"rotation": ["5.5 - math.sin(q.anim_time * 553.8) * 4.0", 0, -3.0]},
            },
        },
        "sneaking": {
            "loop": True,
            "animation_length": 1.2,
            "bones": {
                "Waist": {"position": [0, -1.6, 1.4]},
                "Body": {"rotation": [22.0, 0, 0]},
                "AllHead": {"rotation": [-20.0, 0, 0]},
                "RightLeg": {"rotation": [6.0, 0, 1.5], "position": [0, 1.4, -0.6]},
                "LeftLeg": {"rotation": [6.0, 0, -1.5], "position": [0, 1.4, -0.6]},
                "RightArm": {"rotation": [-18.0, 0, 3.0]},
                "LeftArm": {"rotation": [-18.0, 0, -3.0]},
                "Skirt": {"rotation": [-10.0, 0, 0]},
                "HairBack": {"rotation": [12.0, 0, 0]},
                "HairBackLower": {"rotation": [8.0, 0, 0]},
                "HairFrontRight": {"rotation": [-6.0, 0, 1.5]},
                "HairFrontLeft": {"rotation": [-6.0, 0, -1.5]},
            },
        },
        "sneak": {
            "loop": True,
            "animation_length": 1.1,
            "bones": {
                "Waist": {"position": [0, "-1.6 + math.abs(math.cos(q.anim_time * 327.2)) * 0.35", 1.4]},
                "Body": {"rotation": [22.0, "math.sin(q.anim_time * 327.2) * 2.5", 0]},
                "AllHead": {"rotation": [-20.0, 0, 0]},
                "RightLeg": {"rotation": ["6.0 + math.sin(q.anim_time * 327.2) * 20", 0, 1.5], "position": [0, 1.4, -0.6]},
                "LeftLeg": {"rotation": ["6.0 - math.sin(q.anim_time * 327.2) * 20", 0, -1.5], "position": [0, 1.4, -0.6]},
                "RightArm": {"rotation": ["-18.0 - math.sin(q.anim_time * 327.2) * 14", 0, 3.5]},
                "LeftArm": {"rotation": ["-18.0 + math.sin(q.anim_time * 327.2) * 14", 0, -3.5]},
                "Skirt": {"rotation": [-10.0, 0, 0]},
                "HairBack": {"rotation": ["14.0 + math.abs(math.sin(q.anim_time * 327.2)) * 3.0", 0, 0]},
                "HairBackLower": {"rotation": [10.0, 0, 0]},
                "HairFrontRight": {"rotation": [-5.0, 0, 1.5]},
                "HairFrontLeft": {"rotation": [-5.0, 0, -1.5]},
            },
        },
        "jump": {
            "loop": "hold_on_last_frame",
            "animation_length": 0.45,
            "bones": {
                "Waist": {"position": {"0.0": [0, -0.6, 0], "0.18": [0, 1.0, 0], "0.45": [0, 0.4, 0]}},
                "Body": {"rotation": {"0.0": [4, 0, 0], "0.25": [-3, 0, 0], "0.45": [2, 0, 0]}},
                "RightLeg": {"rotation": {"0.0": [10, 0, 2], "0.22": [-24, 0, 3], "0.45": [-14, 0, 2]}},
                "LeftLeg": {"rotation": {"0.0": [-6, 0, -2], "0.22": [14, 0, -3], "0.45": [8, 0, -2]}},
                "RightArm": {"rotation": {"0.0": [10, 0, 4], "0.22": [-26, 0, 14], "0.45": [-18, 0, 12]}},
                "LeftArm": {"rotation": {"0.0": [10, 0, -4], "0.22": [-26, 0, -14], "0.45": [-18, 0, -12]}},
                "HairBack": {"rotation": {"0.0": [6, 0, 0], "0.25": [22, 0, 0], "0.45": [28, 0, 0]}},
                "HairBackLower": {"rotation": {"0.0": [4, 0, 0], "0.25": [16, 0, 0], "0.45": [22, 0, 0]}},
            },
        },
        "swim": {
            "loop": True,
            "animation_length": 1.2,
            "bones": {
                "Waist": {"rotation": [78, 0, 0], "position": [0, -4.0, 0]},
                "AllHead": {"rotation": [-52, 0, 0]},
                "RightArm": {"rotation": ["-135 + math.sin(q.anim_time * 300) * 28", 0, "14 + math.cos(q.anim_time * 300) * 14"]},
                "LeftArm": {"rotation": ["-135 - math.sin(q.anim_time * 300) * 28", 0, "-14 - math.cos(q.anim_time * 300) * 14"]},
                "RightLeg": {"rotation": ["math.sin(q.anim_time * 300) * 24", 0, 2]},
                "LeftLeg": {"rotation": ["math.sin(q.anim_time * 300) * -24", 0, -2]},
                "HairBack": {"rotation": ["22 + math.sin(q.anim_time * 300) * 6", 0, 0]},
                "HairBackLower": {"rotation": ["18 + math.sin(q.anim_time * 300 - 45) * 8", 0, 0]},
            },
        },
        "swim_stand": {
            "loop": True,
            "animation_length": 1.6,
            "bones": {
                "Waist": {"position": [0, "math.sin(q.anim_time * 225) * 0.8", 0]},
                "RightArm": {"rotation": ["-18 + math.sin(q.anim_time * 225) * 14", 0, "18 + math.cos(q.anim_time * 225) * 10"]},
                "LeftArm": {"rotation": ["-18 - math.sin(q.anim_time * 225) * 14", 0, "-18 - math.cos(q.anim_time * 225) * 10"]},
                "RightLeg": {"rotation": ["math.sin(q.anim_time * 225) * 16", 0, 2]},
                "LeftLeg": {"rotation": ["math.sin(q.anim_time * 225) * -16", 0, -2]},
                "HairBack": {"rotation": ["14 + math.sin(q.anim_time * 225 - 40) * 5", 0, 0]},
                "HairBackLower": {"rotation": ["10 + math.sin(q.anim_time * 225 - 80) * 6", 0, 0]},
            },
        },
        "fly": {
            "loop": True,
            "animation_length": 2.0,
            "bones": {
                "Waist": {"position": [0, "math.sin(q.anim_time * 180) * 1.1", 0], "rotation": [12, 0, 0]},
                "AllHead": {"rotation": [-10, 0, 0]},
                "RightLeg": {"rotation": [16, 0, 3]},
                "LeftLeg": {"rotation": [24, 0, -3]},
                "RightArm": {"rotation": [12, 0, "16 + math.sin(q.anim_time * 180) * 4"]},
                "LeftArm": {"rotation": [12, 0, "-16 - math.sin(q.anim_time * 180) * 4"]},
                "HairBack": {"rotation": ["22 + math.sin(q.anim_time * 180 - 30) * 5", 0, 0]},
                "HairBackLower": {"rotation": ["18 + math.sin(q.anim_time * 180 - 70) * 6", 0, 0]},
            },
        },
        "elytra_fly": {
            "loop": True,
            "animation_length": 1.5,
            "bones": {
                "Waist": {"rotation": [75, 0, 0], "position": [0, -3.5, 0]},
                "AllHead": {"rotation": [-52, 0, 0]},
                "RightArm": {"rotation": [16, 0, 22]},
                "LeftArm": {"rotation": [16, 0, -22]},
                "RightLeg": {"rotation": [12, 0, 3]},
                "LeftLeg": {"rotation": [12, 0, -3]},
                "HairBack": {"rotation": ["28 + math.sin(q.anim_time * 480) * 4", 0, 0]},
                "HairBackLower": {"rotation": ["22 + math.sin(q.anim_time * 480 - 45) * 5", 0, 0]},
            },
        },
        "sit": {
            "loop": True,
            "animation_length": 2.0,
            "bones": {
                "Waist": {"position": [0, -8.2, 0]},
                "Body": {"rotation": [2.0, 0, 0]},
                "RightLeg": {"rotation": [-78, 8, 5]},
                "LeftLeg": {"rotation": [-78, -8, -5]},
                "RightArm": {"rotation": [-22, -8, 6]},
                "LeftArm": {"rotation": [-22, 8, -6]},
                "Skirt": {"rotation": [-24, 0, 0]},
                "HairBack": {"rotation": [14, 0, 0]},
                "HairBackLower": {"rotation": [10, 0, 0]},
            },
        },
        "boat": {
            "loop": True,
            "animation_length": 2.0,
            "bones": {
                "Waist": {"position": [0, -7.8, 0]},
                "RightLeg": {"rotation": [-76, 10, 6]},
                "LeftLeg": {"rotation": [-76, -10, -6]},
                "RightArm": {"rotation": [-28, -6, 6]},
                "LeftArm": {"rotation": [-28, 6, -6]},
                "Skirt": {"rotation": [-24, 0, 0]},
                "HairBack": {"rotation": [14, 0, 0]},
                "HairBackLower": {"rotation": [10, 0, 0]},
            },
        },
        "ride": {
            "loop": True,
            "animation_length": 2.0,
            "bones": {
                "Waist": {"position": [0, -7.2, 0]},
                "RightLeg": {"rotation": [-68, 16, 12]},
                "LeftLeg": {"rotation": [-68, -16, -12]},
                "RightArm": {"rotation": [-34, -10, 6]},
                "LeftArm": {"rotation": [-34, 10, -6]},
                "Skirt": {"rotation": [-20, 0, 0]},
                "HairBack": {"rotation": [14, 0, 0]},
                "HairBackLower": {"rotation": [10, 0, 0]},
            },
        },
        "ride_pig": {
            "loop": True,
            "animation_length": 2.0,
            "bones": {
                "Waist": {"position": [0, -7.2, 0]},
                "RightLeg": {"rotation": [-66, 18, 14]},
                "LeftLeg": {"rotation": [-66, -18, -14]},
                "RightArm": {"rotation": [-32, -8, 6]},
                "LeftArm": {"rotation": [-32, 8, -6]},
                "Skirt": {"rotation": [-20, 0, 0]},
                "HairBack": {"rotation": [14, 0, 0]},
                "HairBackLower": {"rotation": [10, 0, 0]},
            },
        },
        "sleep": {
            "loop": True,
            "animation_length": 3.0,
            "bones": {
                "Waist": {"position": [0, 0, 0]},
                "RightArm": {"rotation": [-12, 0, 6]},
                "LeftArm": {"rotation": [-12, 0, -6]},
                "RightLeg": {"rotation": [4, 0, 2]},
                "LeftLeg": {"rotation": [4, 0, -2]},
                "HairBack": {"rotation": [2, 0, 0]},
            },
        },
        "climb": {
            "loop": True,
            "animation_length": 0.8,
            "bones": {
                "RightArm": {"rotation": ["-95 + math.sin(q.anim_time * 450) * 32", 0, 6]},
                "LeftArm": {"rotation": ["-95 - math.sin(q.anim_time * 450) * 32", 0, -6]},
                "RightLeg": {"rotation": ["-18 - math.sin(q.anim_time * 450) * 26", 0, 2]},
                "LeftLeg": {"rotation": ["-18 + math.sin(q.anim_time * 450) * 26", 0, -2]},
                "HairBack": {"rotation": [10, 0, 0]},
            },
        },
        "climbing": {
            "loop": True,
            "animation_length": 1.0,
            "bones": {
                "RightArm": {"rotation": [-98, 0, 6]},
                "LeftArm": {"rotation": [-82, 0, -6]},
                "RightLeg": {"rotation": [-18, 0, 2]},
                "LeftLeg": {"rotation": [-6, 0, -2]},
                "HairBack": {"rotation": [10, 0, 0]},
            },
        },
        "ladder_up": {
            "loop": True,
            "animation_length": 0.75,
            "bones": {
                "RightArm": {"rotation": ["-105 + math.sin(q.anim_time * 480) * 34", 0, 5]},
                "LeftArm": {"rotation": ["-105 - math.sin(q.anim_time * 480) * 34", 0, -5]},
                "RightLeg": {"rotation": ["-20 - math.sin(q.anim_time * 480) * 26", 0, 2]},
                "LeftLeg": {"rotation": ["-20 + math.sin(q.anim_time * 480) * 26", 0, -2]},
                "HairBack": {"rotation": [12, 0, 0]},
            },
        },
        "ladder_stillness": {
            "loop": True,
            "animation_length": 1.5,
            "bones": {
                "RightArm": {"rotation": [-95, 0, 5]},
                "LeftArm": {"rotation": [-95, 0, -5]},
                "RightLeg": {"rotation": [-12, 0, 2]},
                "LeftLeg": {"rotation": [-12, 0, -2]},
                "HairBack": {"rotation": [8, 0, 0]},
            },
        },
        "ladder_down": {
            "loop": True,
            "animation_length": 0.75,
            "bones": {
                "RightArm": {"rotation": ["-95 - math.sin(q.anim_time * 480) * 30", 0, 5]},
                "LeftArm": {"rotation": ["-95 + math.sin(q.anim_time * 480) * 30", 0, -5]},
                "RightLeg": {"rotation": ["-18 + math.sin(q.anim_time * 480) * 24", 0, 2]},
                "LeftLeg": {"rotation": ["-18 - math.sin(q.anim_time * 480) * 24", 0, -2]},
                "HairBack": {"rotation": [12, 0, 0]},
            },
        },
        "swing_hand": {
            "loop": False,
            "animation_length": 0.32,
            "bones": {
                "Body": {"rotation": {"0.0": [0, 0, 0], "0.10": [4, -10, 0], "0.32": [0, 0, 0]}},
                "RightArm": {
                    "rotation": {
                        "0.0": [-20, 0, 4],
                        "0.08": [-110, 12, 8],
                        "0.20": [-38, -14, 2],
                        "0.32": [0, 0, 0],
                    }
                },
            },
        },
        "swing_offhand": {
            "loop": False,
            "animation_length": 0.32,
            "bones": {
                "Body": {"rotation": {"0.0": [0, 0, 0], "0.10": [4, 10, 0], "0.32": [0, 0, 0]}},
                "LeftArm": {
                    "rotation": {
                        "0.0": [-20, 0, -4],
                        "0.08": [-110, -12, -8],
                        "0.20": [-38, 14, -2],
                        "0.32": [0, 0, 0],
                    }
                },
            },
        },
        "use_mainhand": {
            "loop": True,
            "animation_length": 0.5,
            "bones": {
                "RightArm": {"rotation": [-52, 16, -4]},
            },
        },
        "use_offhand": {
            "loop": True,
            "animation_length": 0.5,
            "bones": {
                "LeftArm": {"rotation": [-52, -16, 4]},
            },
        },
        "attacked": {
            "loop": False,
            "animation_length": 0.35,
            "bones": {
                "Body": {"rotation": {"0.0": [0, 0, 0], "0.10": [-14, 0, 4], "0.35": [0, 0, 0]}},
                "AllHead": {"rotation": {"0.0": [0, 0, 0], "0.10": [-10, 0, -4], "0.35": [0, 0, 0]}},
                "RightArm": {"rotation": {"0.0": [0, 0, 0], "0.12": [-24, 0, 16], "0.35": [0, 0, 0]}},
                "LeftArm": {"rotation": {"0.0": [0, 0, 0], "0.12": [-24, 0, -16], "0.35": [0, 0, 0]}},
                "HairBack": {"rotation": {"0.0": [4, 0, 0], "0.12": [22, 0, 0], "0.35": [4, 0, 0]}},
            },
        },
        "death": {
            "loop": "hold_on_last_frame",
            "animation_length": 0.55,
            "bones": {
                "Waist": {
                    "rotation": {"0.0": [0, 0, 0], "0.55": [0, 0, 86]},
                    "position": {"0.0": [0, 0, 0], "0.55": [-10, -10, 0]},
                },
                "RightArm": {"rotation": {"0.0": [0, 0, 0], "0.55": [-18, 0, 22]}},
                "LeftArm": {"rotation": {"0.0": [0, 0, 0], "0.55": [-12, 0, -18]}},
                "HairBack": {"rotation": {"0.0": [4, 0, 0], "0.55": [12, 0, 10]}},
            },
        },
        # Parallel gentle ambient hair breeze layer (subtle & non-intrusive)
        "parallel0": {
            "loop": True,
            "animation_length": 4.0,
            "bones": {
                "HairBack": {"rotation": ["math.sin(q.anim_time * 90) * 1.4", 0, "math.cos(q.anim_time * 90) * 0.9"]},
                "HairBackLower": {"rotation": ["math.sin(q.anim_time * 90 - 45) * 1.8", 0, "math.cos(q.anim_time * 90 - 45) * 1.1"]},
                "HairFrontRight": {"rotation": ["math.sin(q.anim_time * 90 - 20) * 0.8", 0, 0]},
                "HairFrontLeft": {"rotation": ["math.sin(q.anim_time * 90 - 20) * 0.8", 0, 0]},
            },
        },
    }
    return {"format_version": "1.8.0", "animations": anims}


def build_arm_animations() -> dict:
    """Clean YSM 2.6.0 item-use arm animations matching our RightArm/LeftArm/RightHand/LeftHand skeleton."""
    return {
        "format_version": "1.8.0",
        "animations": {
            "use_mainhand:eat": {
                "loop": True,
                "animation_length": 0.4,
                "bones": {
                    "RightArm": {
                        "rotation": {
                            "0.0": [-76, 22, -6],
                            "0.2": [-86, 26, -8],
                            "0.4": [-76, 22, -6],
                        }
                    },
                    "RightHand": {"rotation": [-16, 0, 0]},
                },
            },
            "use_mainhand:drink": {
                "loop": True,
                "animation_length": 0.4,
                "bones": {
                    "RightArm": {
                        "rotation": {
                            "0.0": [-84, 20, -6],
                            "0.2": [-92, 22, -6],
                            "0.4": [-84, 20, -6],
                        }
                    },
                    "RightHand": {"rotation": [-18, 0, 0]},
                },
            },
            "use_mainhand:bow": {
                "loop": "hold_on_last_frame",
                "animation_length": 0.35,
                "bones": {
                    "RightArm": {"rotation": {"0.0": [-38, 0, 0], "0.35": [-90, 14, 4]}},
                    "LeftArm": {"rotation": {"0.0": [-38, 0, 0], "0.35": [-86, -30, -6]}},
                },
            },
            "use_mainhand:shield": {
                "loop": True,
                "bones": {
                    "RightArm": {"rotation": [-46, 24, -10]},
                },
            },
            "use_offhand:shield": {
                "loop": True,
                "bones": {
                    "LeftArm": {"rotation": [-46, -24, 10]},
                },
            },
        },
    }


def build_ysm_manifest() -> dict:
    return {
        "spec": 2,
        "metadata": {
            "name": "骷髅兜帽少女 (Skull Hoodie Girl)",
            "tips": "奶白淡紫长发立体骷髅兜帽少女自定义 YSM 2.6.0 模型\n包含 3D 立体骷髅兜帽、独立 3×2 像素眼部图层、多层片状长发、胸前与鞋面立体小骷髅饰品、第一人称宽袖手臂及全套基础动作。",
            "license": {
                "type": "CC-BY-NC-SA 4.0",
                "desc": "Custom YSM 2.6.0 model built from user 3-view turnaround.",
            },
            "authors": [
                {
                    "name": "Antigravity Designer",
                    "role": "3D Modeling / Pixel Texturing / Rigging / Base Animations",
                    "comment": "Built & verified to YSM 2.6.0 specification",
                }
            ],
        },
        "properties": {
            "height_scale": 0.94,
            "width_scale": 0.92,
            "preview_animation": "gui",
            "disable_preview_rotation": False,
        },
        "files": {
            "player": {
                "model": {
                    "main": "models/main.json",
                    "arm": "models/arm.json",
                },
                "animation": {
                    "main": "animations/main.animation.json",
                    "arm": "animations/arm.animation.json",
                },
                "texture": [
                    "textures/default.png",
                ],
            },
            "language_path": "lang",
        },
    }


def main():
    _write_json(PACK_DIR / "animations" / "main.animation.json", build_main_animations())
    _write_json(PACK_DIR / "animations" / "arm.animation.json", build_arm_animations())
    _write_json(PACK_DIR / "ysm.json", build_ysm_manifest())
    _write_json(
        PACK_DIR / "lang" / "zh_cn.json",
        {
            "model.skull_hoodie_girl.name": "骷髅兜帽少女",
            "model.skull_hoodie_girl.desc": "立体骷髅兜帽与极浅淡紫长发少女模型",
        },
    )
    _write_json(
        PACK_DIR / "lang" / "en_us.json",
        {
            "model.skull_hoodie_girl.name": "Skull Hoodie Girl",
            "model.skull_hoodie_girl.desc": "3D voxel skull hoodie & pale lavender long-hair girl YSM model",
        },
    )
    print(f"Generated YSM 2.6.0 animations, manifest & lang files in {PACK_DIR}")


if __name__ == "__main__":
    main()
