# This script can populate per-pair elevation fields in link
# profiles based on data it fetches from Databricks (requires
# an ECT Databricks access token).
#
# This will be the ancestor of the eventual channel tool command to do
# this. Since it's temporary, correctness is the only priority.
#
# The script currently only supports manipulating TXO channels.

if __name__ != "__main__":
    import sys

    sys.exit("do not import this script")

import argparse
import os
import re
import subprocess
from copy import deepcopy
from enum import Enum

from databricks import sql
from ruamel.yaml import YAML

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)


class Directionality(Enum):
    TXO = 1
    BIDIR = 2


BITRATE_SCALE_FACTOR = 0.9
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_TOKEN")

command_history = {}


def channel_tool(args):
    if not isinstance(args, list):
        raise Exception("Expected list")

    args = [str(a) for a in args]

    command = ["poetry", "run", "python", "-m", "channel_tool"] + args
    command_str = " ".join(command)
    print(command_str)

    if command_str in command_history:
        return command_history[command_str].stdout

    process = subprocess.run(command, capture_output=True, timeout=120)

    if process.returncode != 0:
        raise Exception(
            f"Channel tool failed. stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )

    command_history[command_str] = deepcopy(process)

    return process.stdout


def fetch_data(table):
    connection = sql.connect(
        server_hostname="dbc-24e0a945-16d8.cloud.databricks.us",
        http_path="/sql/1.0/warehouses/c9cc905ac4a154ae",
        access_token=DATABRICKS_ACCESS_TOKEN,
    )

    cursor = connection.cursor()

    query = f"""
        SELECT *
        FROM {table}
        WHERE gs_id = 'smags' and band = 'S' and pls in (7, 15, 23, 27)
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    return rows


def get_asset_type(asset_id):
    regex = re.compile("^FM.*$")
    if regex.match(asset_id):
        return "sat"
    else:
        return "gs"


def asset_filepath(asset_id):
    asset_type = get_asset_type(asset_id)

    return f"{args.environment}/{asset_type}/{asset_id}.yaml"


def load_config_file(asset_id):
    filename = asset_filepath(asset_id)

    with open(filename, "r") as file:
        channel_config_file = yaml.load(file)

    return channel_config_file


parser = argparse.ArgumentParser()
parser.add_argument(
    "-e", "--environment", choices=["staging", "production"], required=True
)
args = parser.parse_args()

if not DATABRICKS_ACCESS_TOKEN:
    raise Exception("DATABRICKS_TOKEN environment variable is missing")

yaml = YAML()

per_pair_rows = fetch_data("ripley_dev.default.optimal_channel_properties")
per_asset_rows = fetch_data("ripley_dev.default.optimal_channel_properties_gs")

# Get rid of decommissioned assets
per_pair_rows = [
    row
    for row in per_pair_rows
    if os.path.exists(asset_filepath(row.gs_id))
    and os.path.exists(asset_filepath(row.spire_id))
]
per_asset_rows = [
    row for row in per_asset_rows if os.path.exists(asset_filepath(row.gs_id))
]

configs = {}
for r in per_pair_rows:
    if r.spire_id not in configs:
        configs[r.spire_id] = load_config_file(r.spire_id)
    if r.gs_id not in configs:
        configs[r.gs_id] = load_config_file(r.gs_id)

for row in per_pair_rows:
    gs_id = row.gs_id
    spire_id = row.spire_id

    sat_config = configs[spire_id]
    gs_config = configs[gs_id]

    # for directionality in list(Directionality):
    directionality = Directionality.TXO

    print(
        f"\033[93mProcessing {gs_id} {spire_id} {row.band}-Band {row.bw_mhz}MHZ {row.pls}PLS {directionality.name}\033[00m"
    )

    predicate = (
        f"directionality == '{directionality.name}' and "
        "provider == 'SPIRE' and "  # Ripley doesn't process KSAT ground telemetry yet
        f"space_ground_{row.band.lower()}band_bandwidth_mhz == {row.bw_mhz} and "
        "(space_ground_xband or space_ground_sband_encoding == 'DVBS2X')"
    )

    def dupe(asset):
        channel_tool(
            [
                "duplicate",
                args.environment,
                asset,
                predicate,
                "--pls",
                row.pls,
                "--bitrate",
                row.mbps * 1000 * BITRATE_SCALE_FACTOR,
                "--min-elevation",
                int(row.elevation),
                "-y",
            ]
        )

    dupe(gs_id)
    dupe(spire_id)

    # We have to reload templates after every duplication because it also
    # creates templates
    with open("gs_templates.yaml") as file:
        templates = yaml.load(file)

    # Insert per-pair elevation values to gs side link profiles

    # get the channels and their link profiles that match our predicate
    # this includes all newly created channels as well as any existing ones
    channels = channel_tool(
        ["query", args.environment, gs_id, predicate, "link_profile"]
    )

    decoded = channels.decode("utf-8")

    # query dumps three fields in csv format: asset, channel, value
    channels = {}
    for line in decoded.splitlines()[1:]:
        fields = line.split(",", maxsplit=2)
        assert fields[0] == gs_id
        channels[fields[1]] = yaml.load(fields[2])

    for channel, link_profile in channels.items():
        temp_filename = f"/tmp/{gs_id}_{channel}.yaml"
        class_annos = templates[channel]["classification_annotations"]
        pls = class_annos[f"space_ground_{row.band.lower()}band_dvbs2x_pls"]
        bw_mhz = class_annos[f"space_ground_{row.band.lower()}band_bandwidth_mhz"]

        # we're doing just TXO for now
        assert class_annos["directionality"] == "TXO"

        dvb_link_profile = max(link_profile, key=lambda i: i["downlink_rate_kbps"])

        dvb_link_profile.pop("min_elevation_deg", None)

        # Default comes from the per-asset table which contains the average
        # performance of an asset across all of its contacts
        # This will fail for existing channels whose PLS value is not in
        # included in the query. We delete them and move on.
        try:
            default_min_elevation_deg = int(
                next(
                    (
                        x
                        for x in per_asset_rows
                        if x.gs_id == gs_id and x.pls == pls and x.bw_mhz == bw_mhz
                    )
                ).elevation
            )
        except StopIteration:
            channel_tool(
                [
                    "delete",
                    args.environment,
                    gs_id,
                    channel,
                    "-y",
                ]
            )
            continue

        dvb_link_profile["default_min_elevation_deg"] = default_min_elevation_deg
        dvb_link_profile["downlink_rate_kbps"] = r.mbps * 1000 * BITRATE_SCALE_FACTOR

        # create a list of dicts that contain elevation to satellite lists
        satellite_min_elevations = []
        for r in per_pair_rows:
            # poor man's filter
            if r.gs_id != gs_id or r.pls != pls or r.bw_mhz != bw_mhz:
                continue

            exists = False
            for sme in satellite_min_elevations:
                if sme["min_elevation_deg"] == int(r.elevation):
                    if row.spire_id not in sme["satellites"]:
                        sme["satellites"].append(r.spire_id)
                    exists = True
                    break

            if not exists:
                satellite_min_elevations.append(
                    {
                        "min_elevation_deg": int(r.elevation),
                        "satellites": [r.spire_id],
                    }
                )

        if satellite_min_elevations:
            dvb_link_profile["satellite_min_elevations"] = satellite_min_elevations

        if directionality == Directionality.TXO:
            lp = [dict(dvb_link_profile)]
        else:
            uhf_link_profile = min(link_profile, key=lambda i: i["downlink_rate_kbps"])
            lp = [dict(uhf_link_profile), dict(dvb_link_profile)]

        with open(temp_filename, "wb") as file:
            yaml.dump(lp, file)

        channel_tool(
            [
                "edit",
                args.environment,
                gs_id,
                channel,
                "--mode",
                "overwrite",
                "--link_profile_file",
                temp_filename,
                "-y",
            ]
        )

channel_tool(["normalize", args.environment, "all"])
channel_tool(["format"])
