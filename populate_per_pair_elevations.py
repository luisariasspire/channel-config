# This script can populate per-pair elevation fields in link
# profiles based on data it fetches from Databricks (requires
# an ECT Databricks access token).
#
# This will be the ancestor of the eventual channel tool command to do
# this. Since it's temporary, correctness is the only priority.

if __name__ != "__main__":
    import sys

    sys.exit("do not import this script")

import argparse
import json
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
    print(command_str, flush=True)

    if command_str in command_history:
        return command_history[command_str].stdout

    process = subprocess.run(command, capture_output=True, timeout=600)

    if process.returncode != 0:
        raise Exception(
            f"Channel tool failed. stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )

    command_history[command_str] = deepcopy(process)

    return process.stdout


def fetch_data(query):
    connection = sql.connect(
        server_hostname="dbc-24e0a945-16d8.cloud.databricks.us",
        http_path="/sql/1.0/warehouses/c9cc905ac4a154ae",
        access_token=DATABRICKS_ACCESS_TOKEN,
    )

    cursor = connection.cursor()

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


def get_channel_link_profile(gs_id, predicate):
    channels = channel_tool(
        ["query", args.environment, gs_id, predicate, "link_profile"]
    )

    decoded = channels.decode("utf-8")
    result = decoded.splitlines()[1:]

    assert len(result) == 1

    fields = result[0].split(",", maxsplit=2)

    assert fields[0] == gs_id

    # (channel_id, link_profile)
    return (fields[1], yaml.load(fields[2]))


parser = argparse.ArgumentParser()
parser.add_argument(
    "-e", "--environment", choices=["staging", "production"], required=True
)
args = parser.parse_args()

if not DATABRICKS_ACCESS_TOKEN:
    raise Exception("DATABRICKS_TOKEN environment variable is missing")

yaml = YAML()
new_channels = fetch_data(
    """
with aq as (
select 
gs_id, collect_set(spire_id) as satellites, pls, round(elevation) as min_elevation_deg, bw_mhz, band, any_value(mbps) as mbps
from ripley_dev.default.optimal_channel_properties
-- CHANGE PER-GS
where (
    (gs_id = "ancgs" and band = 'S' and pls in (15, 23, 31, 39) and bw_mhz = 1)
    or
    (gs_id = "ancgs" and band = 'S' and pls in (7, 15, 23, 31) and bw_mhz = 5)
    or
    (gs_id = "bdugs" and band = 'S' and pls in (19, 27, 39, 75) and bw_mhz = 1)
    or
    (gs_id = "bdugs" and band = 'S' and pls in (7, 15, 23, 27) and bw_mhz = 5)
    or
    (gs_id = "vntgs" and band = 'S' and pls in (43, 79, 87, 91) and bw_mhz = 1)
    or
    (gs_id = "vntgs" and band = 'S' and pls in (19, 27, 43, 75) and bw_mhz = 5)
    or
    (gs_id = "puqgs" and band = 'S' and pls in (23, 39, 75, 83) and bw_mhz = 1)
    or
    (gs_id = "accgs" and band = 'S' and pls in (23, 35, 75, 91) and bw_mhz = 1)
)
group by gs_id, pls, round(elevation), bw_mhz, band
)
select aq.gs_id, collect_list(struct(aq.min_elevation_deg, aq.satellites)) as satellite_min_elevations, aq.pls, aq.bw_mhz, aq.band, aq.mbps, coalesce(round(gs.elevation), 90) as default_min_elevation_deg
from aq
left join ripley_dev.default.optimal_channel_properties_gs gs on aq.gs_id = gs.gs_id and aq.pls = gs.pls and aq.bw_mhz = gs.bw_mhz and aq.band = gs.band
group by aq.gs_id, aq.pls, aq.bw_mhz, aq.band, aq.mbps, gs.elevation
"""
)
active_sats = fetch_data(
    "select asset_id from ripley_dev.default.active_assets where asset_type = 'sat'"
)

# We get a list of pls values from databricks but for various reasons we may not
# process them. e.g. if all the assets under that pls value are decommisioned.
# So let's keep track of what we processed.
new_pls_values = {}

high_mid_freq = ["accgs", "puqgs"]
supports_bidir = ["bdugs"]

for row in new_channels:
    # skip if the gs is decomissioned
    if not os.path.exists(asset_filepath(row.gs_id)):
        continue

    gs_id = row.gs_id
    pls = row.pls
    bw_mhz = row.bw_mhz
    band = row.band.lower()
    downlink_rate_kbps = row.mbps * 1000 * BITRATE_SCALE_FACTOR
    satellite_min_elevations = json.loads(row.satellite_min_elevations)
    default_min_elevation_deg = int(row.default_min_elevation_deg)

    supported_directionality = [Directionality.TXO]
    if gs_id in supports_bidir:
        supported_directionality.append(Directionality.BIDIR)

    for directionality in supported_directionality:
        # clean out decomissioned satellites
        for d in satellite_min_elevations:
            d["satellites"] = [
                v for v in d["satellites"] if os.path.exists(asset_filepath(v))
            ]

        # Some of these may be empty afterwards. Filter them out.
        satellite_min_elevations = [
            i for i in satellite_min_elevations if i["satellites"]
        ]

        # Finally, add all satellites that doesn't have an override under 90
        # degree bucket to disable them.
        disabled_sats = [
            sat.asset_id
            for sat in active_sats
            if all(
                sat.asset_id not in d["satellites"] for d in satellite_min_elevations
            )
        ]
        satellite_min_elevations.append(
            {"min_elevation_deg": 90, "satellites": disabled_sats}
        )

        mid_freq = 2200.5 if gs_id in high_mid_freq else 2022.5

        predicate = (
            f"directionality == '{directionality.name}' and "
            # CHANGE PER-GS
            "provider == 'SPIRE' and "
            f"space_ground_{band}band_bandwidth_mhz == {bw_mhz} and "
            "(space_ground_xband or space_ground_sband_encoding == 'DVBS2X') and "
            # CHANGE PER-GS
            f"(not space_ground_sband_mid_freq_mhz or space_ground_sband_mid_freq_mhz == {mid_freq})"
        )

        comma_separated_assets = (
            ",".join(
                ",".join(d["satellites"])
                for d in satellite_min_elevations
                # Make sure we don't create a channel for disabled sats
                # They're disabled to ensure we don't communicate with this groundstation
                # if the sat gets the channel by some other means in the future.
                if d["min_elevation_deg"] != 90
            )
            + ","
            + gs_id
        )

        channel_tool(
            [
                "duplicate",
                args.environment,
                comma_separated_assets,
                predicate,
                "--pls",
                pls,
                "--bitrate",
                downlink_rate_kbps,
                "--min-elevation",
                int(default_min_elevation_deg),
                "-y",
            ]
        )

        new_pls_values.setdefault((gs_id, band, bw_mhz, directionality), []).append(pls)

        edit_predicate = predicate + f" and space_ground_{band}band_dvbs2x_pls == {pls}"

        # the channel_id and the link_profile of the channel we just created
        (channel_id, link_profile) = get_channel_link_profile(gs_id, edit_predicate)

        dvb_link_profile = max(link_profile, key=lambda i: i["downlink_rate_kbps"])
        dvb_link_profile["satellite_min_elevations"] = satellite_min_elevations

        config_file = load_config_file(gs_id)
        if "dynamic_window_parameters" in config_file[channel_id]:
            dvb_link_profile["add_transmit_times"] = True
            subprocess.run(
                [
                    "yq",
                    "-i",
                    f"del(.{channel_id}.dynamic_window_parameters)",
                    asset_filepath(gs_id),
                ],
            )
            subprocess.run(
                [
                    "yq",
                    "-i",
                    f"del(.{channel_id}.dynamic_window_parameters)",
                    "gs_templates.yaml",
                ]
            )

        # if we duplicated a channel that uses the old key, replace it.
        if dvb_link_profile.pop("min_elevation_deg", None):
            dvb_link_profile["default_min_elevation_deg"] = default_min_elevation_deg

        lp = [dict(dvb_link_profile)]

        if directionality == Directionality.BIDIR:
            uhf_link_profile = min(link_profile, key=lambda i: i["downlink_rate_kbps"])
            uhf_default_min_elevation_deg = uhf_link_profile.pop(
                "min_elevation_deg", None
            )
            # if we duplicated a channel that uses the old key, replace it.
            if uhf_default_min_elevation_deg:
                uhf_link_profile[
                    "default_min_elevation_deg"
                ] = uhf_default_min_elevation_deg
            # validation rules expect uhf to be the first.
            lp.insert(0, dict(uhf_link_profile))

        tmp_file = f"./bundle/{gs_id}_{channel_id}.yaml"

        with open(tmp_file, "wb") as file:
            yaml.dump(lp, file)

        channel_tool(
            [
                "edit",
                args.environment,
                gs_id,
                channel_id,
                "--mode",
                "overwrite",
                "--link_profile_file",
                tmp_file,
                "-y",
            ]
        )

# Delete all channels that contain an unsupport pls value on the ground station.
for (gs_id, band, bw_mhz, directionality), pls_values in new_pls_values.items():
    predicate = (
        f"directionality == '{directionality.name}' and "
        "provider == 'SPIRE' and "
        f"space_ground_{band}band_bandwidth_mhz == {bw_mhz} and "
        "(space_ground_xband or space_ground_sband_encoding == 'DVBS2X') and "
        f"space_ground_{band}band_dvbs2x_pls not in {pls_values}"
    )

    channel_tool(
        [
            "delete",
            args.environment,
            gs_id,
            predicate,
            "-y",
        ]
    )

channel_tool(["normalize", args.environment, "all"])
channel_tool(["format"])
