#!/usr/bin/env python3

import argparse
import copy
import shutil
import datetime
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from io import StringIO

## Comment added in user config file when new parameters are added
NEW_PARAMS_COMMENT = f"NEW PARAMETERS ADDED BY UPDATED TEMPLATE ({datetime.datetime.now().strftime('%d-%m-%Y %X')}) --> See template to check parameter(s) description"

def deep_merge_defaults(template, user, added_keys=None, path=""):
    """
    Returns user updated with the missing keys from template.
    The values defined in user are always retained.

    Additionally, when new keys are added in the same YAML level,
    a comment is inserted above the first one
    """
    if added_keys is None:
        added_keys = []

    if user is None:
        added_keys.append(path or "<root>")
        return copy.deepcopy(template), added_keys

    if isinstance(template, dict) and isinstance(user, dict):
        comment_added_in_this_level = False

        for key, template_value in template.items():
            current_path = f"{path}.{key}" if path else str(key)

            if key not in user:
                user[key] = copy.deepcopy(template_value)
                added_keys.append(current_path)

                if not comment_added_in_this_level and isinstance(user, CommentedMap):
                    user.yaml_set_comment_before_after_key(
                        key,
                        before=NEW_PARAMS_COMMENT,
                    )
                    comment_added_in_this_level = True

            else:
                user[key], added_keys = deep_merge_defaults(
                    template_value,
                    user[key],
                    added_keys,
                    current_path,
                )

    return user, added_keys


def find_extra_keys(template, user, extra_keys=None, path=""):
    """
    Detects keys existing in user but not in template (probable legacy parameters).
    They are not removed, only reported
    """
    if extra_keys is None:
        extra_keys = []

    if isinstance(template, dict) and isinstance(user, dict):
        for key in user:
            current_path = f"{path}.{key}" if path else str(key)

            if key not in template:
                extra_keys.append(current_path)
            else:
                find_extra_keys(template[key], user[key], extra_keys, current_path)

    return extra_keys


def load_yaml(yaml, path):
    if not path.exists():
        return CommentedMap()

    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    return data if data is not None else CommentedMap()

def ensure_blank_line_before_new_params_comment(text):
    """
    Ensures that a new line is added before the NEW_PARAMS_COMMENT
    """
    lines = text.splitlines()
    output = []

    marker = f"# {NEW_PARAMS_COMMENT}"

    for line in lines:
        if line.strip() == marker:
            if output and output[-1].strip() != "":
                output.append("")
        output.append(line)

    return "\n".join(output) + "\n"


def save_yaml(yaml, path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    buffer = StringIO()
    yaml.dump(data, buffer)

    content = buffer.getvalue()
    content = ensure_blank_line_before_new_params_comment(content)

    with path.open("w", encoding="utf-8") as f:
        f.write(content)

def sync_file(template_path, config_path, backup=True, report_extra=True):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    template_data = load_yaml(yaml, template_path)
    user_data = load_yaml(yaml, config_path)

    updated_data, added_keys = deep_merge_defaults(template_data, user_data)

    extra_keys = []
    if report_extra:
        extra_keys = find_extra_keys(template_data, updated_data)

    if added_keys:
        if backup and config_path.exists():
            backup_path = config_path.with_suffix(config_path.suffix + ".bak")
            shutil.copy2(config_path, backup_path)

        save_yaml(yaml, config_path, updated_data)

    return added_keys, extra_keys


def main():
    parser = argparse.ArgumentParser(
        description="Updates YAML files from user adding new parameters from templates"
    )
    parser.add_argument(
        "--template",
        required=True,
        type=Path,
        help="Path to template file",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to user config file",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak copy of user config file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not show change report",
    )

    args = parser.parse_args()

    added_keys, extra_keys = sync_file(
        template_path=args.template,
        config_path=args.config,
        backup=not args.no_backup,
    )

    if not args.quiet:

        if added_keys or extra_keys: ## Print report only is there are any changes to report
            print(f"Config: {args.config}")

            if added_keys:
                print("Added keys from template:")
                for key in added_keys:
                    print(f"  + {key}")
                if not args.no_backup:
                    print(f"Backup of original user config stored in {args.config.with_suffix(args.config.suffix + '.bak')}")

            if extra_keys:
                print("Keys in user config not present on template:")
                for key in extra_keys:
                    print(f"  ? {key}")

            print("")

if __name__ == "__main__":
    main()