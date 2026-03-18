import yaml
import json
import os

with open("config.yml", "r", encoding="utf-8") as _f:
    config = yaml.safe_load(_f)

lang_directory = "lang"
current_language_code = config.get("LANGUAGE", "en")
valid_language_codes = []

for _filename in os.listdir(lang_directory):
    if _filename.startswith("lang.") and _filename.endswith(".json"):
        valid_language_codes.append(_filename.split(".")[1])


def load_current_language() -> dict:
    path = os.path.join(lang_directory, f"lang.{current_language_code}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_instructions() -> dict:
    instructions = {}
    instructions_dir = "instructions"
    if not os.path.exists(instructions_dir):
        return instructions
    for file_name in os.listdir(instructions_dir):
        if file_name.endswith(".txt"):
            path = os.path.join(instructions_dir, file_name)
            with open(path, "r", encoding="utf-8") as f:
                instructions[file_name.split(".")[0]] = f.read()
    return instructions


def load_active_channels() -> dict:
    if os.path.exists("channels.json"):
        with open("channels.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Lucky Bot — Rewritten
