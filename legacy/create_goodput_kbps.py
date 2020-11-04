#! /usr/bin/env python3

# This script sets all of the goodput values to default based on the legacy asset profiler.

# To generate and apply all of the default values run the following from the legacy folder
# pipenv run python create_goodput_kbps.py [production,staging]

import argparse
from ruamel.yaml import YAML
import os

yaml = YAML()
with open("legacy_asset_profiles.yaml") as f:
    DEFAULT_RATES = yaml.load(f)["default_rates"]

TK_DOMAINS = {"staging": "sbox", "production": "cloud"}

PARSER = argparse.ArgumentParser(
    description="A tool for setting the goodput the constellation."
)

PARSER.add_argument(
    "environment",
    choices=["staging", "production"],
    type=str,
    help="Which environment to configure.",
)


def update_goodput(env: str):
    for asset_type in ['gs', 'sat']:
        directory = f'../{env}/{asset_type}'
        for filename in os.listdir(directory):
            with open(os.path.join(directory, filename)) as f:
                channel_configs = yaml.load(f)
            for name, properties in channel_configs.items():
                goodput = DEFAULT_RATES.get(name)
                if goodput is None:
                    print(f'No default rate for {name} defined! Skipping!')
                else:
                    properties['goodput_kbps'] = goodput
            with open(os.path.join(directory, filename), "w") as f:
                yaml.dump(channel_configs, f)


def main():
    args = PARSER.parse_args()
    update_goodput(args.environment)


if __name__ == "__main__":
    main()
