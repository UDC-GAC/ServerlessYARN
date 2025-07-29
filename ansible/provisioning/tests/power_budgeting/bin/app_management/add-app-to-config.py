import sys
from pathlib import Path
from ruamel.yaml import YAML


def add_app_to_config(file, app):
    # Load config file
    out = Path(file)
    yaml_utils = YAML()
    yaml_utils.default_flow_style = False
    yaml_utils.preserve_quotes = True
    data = yaml_utils.load(out)

    # Change "apps" field in config
    if "apps" in data:
        data["apps"] = app

    # Write updated config
    yaml_utils.dump(data, out)


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("At least 2 arguments are needed")
        print("1 -> Configuration file")
        print("2 -> App directory")
        sys.exit(0)

    config_file = str(sys.argv[1])
    app_dir = str(sys.argv[2])

    add_app_to_config(config_file, app_dir)

