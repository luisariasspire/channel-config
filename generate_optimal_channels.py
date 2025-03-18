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
JIRA_TICKET_ID = "PRI-211"

command_history = {}


def hash_asset_pair(gs_id, spire_id):
    hash_value = 0

    for char in gs_id:
        hash_value = hash_value * 31 + ord(char)

    for char in spire_id:
        hash_value = hash_value * 31 + ord(char)

    return hash_value


def channel_tool(args):
    if not isinstance(args, list):
        raise Exception("Expected list")

    command = ["poetry", "run", "python", "-m", "channel_tool"] + args
    command_str = " ".join(command)
    print(command_str)

    if command_str in command_history:
        return command_history[command_str].stdout

    process = subprocess.run(command, capture_output=True, timeout=120)

    if process.returncode != 0:
        raise Exception(f"Channel tool failed with {process.stdout}")

    command_history[command_str] = deepcopy(process)

    return process.stdout


# Merge two forward channel definitions, giving priority to d2
# Doesn't cover most edge cases of merging arbitrary dicts
# Replaces the value with d2's for shared keys for all types
# except for dicts which are recursed.
def merge_forward_channels(d1, d2):
    assert isinstance(d1, dict) and isinstance(d2, dict)
    d = deepcopy(d1)
    for key in d2:
        if key not in d1:
            d[key] = d2[key]
        elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
            merged = merge_forward_channels(d1[key], d2[key])
            d[key] = merged
        elif type(d1[key]) != type(d2[key]):
            raise Exception()
        else:
            d[key] = d2[key]

    return d


def gen_channel_id(row, directionality):
    return f"{row.gs_id}_{row.spire_id}_{directionality.name}_{row.band}BAND_{row.pls}PLS_{int(row.bw_mhz)}MHZ_{JIRA_TICKET_ID}"


def gen_class_annos(row, original_class_annos):
    return {
        **original_class_annos,
        f"space_ground_{row.band.lower()}band_dvbs2x_pls": row.pls,
        f"space_ground_{row.band.lower()}band_bandwidth_mhz": row.bw_mhz,
        # HACK
        # Append a numeric hash of the asset pair to the Jira ticket ID
        # so that it's unique for each channels
        "jira_ticket": f"{JIRA_TICKET_ID}{hash_asset_pair(row.gs_id, row.spire_id)}",
    }


def gen_forward_channel(row):
    stdout = channel_tool(
        [
            "pls",
            "--radionet",
            f"--{row.band.lower()}band",
            "--pls",
            str(row.pls),
            "--raw",
        ]
    )

    return yaml.load(stdout)


def gen_link_profile(row, directionality, original_link_profile):
    dvb_profile = max(original_link_profile, key=lambda i: i["min_elevation_deg"])

    link_profile = [
        {
            **dvb_profile,
            "min_elevation_deg": float(row.elevation),
            "downlink_rate_kbps": round(row.mbps * BITRATE_SCALE_FACTOR * 1000, 2),
        }
    ]

    if directionality == Directionality.BIDIR:
        uhf_profile = min(original_link_profile, key=lambda i: i["min_elevation_deg"])

        link_profile.append(uhf_profile)

    return deepcopy(link_profile)


def gen_dynamic_window_parameters(row, original_dynamic_window_parameters):
    if not original_dynamic_window_parameters:
        return None

    return {"transmit_times": {"elevation_threshold_deg": float(row.elevation)}}


def gen_window_parameters(row, directionality, original_window_parameters):
    forward_channels = []

    if directionality == Directionality.BIDIR:
        forward_channels.append({"radio_band": "UHF"})

    original_dvb_forward_channel = [
        fc
        for fc in original_window_parameters.get("forward_channels", [])
        if fc.get("radio_band", "") != "UHF"
    ]

    dvb_fc = gen_forward_channel(row)["forward_channels"][0]

    if not original_dvb_forward_channel:
        forward_channels.append(dvb_fc)
        return {"forward_channels": deepcopy(forward_channels)}

    original_dvb_forward_channel = original_dvb_forward_channel[0]

    dvb_forward_channel = merge_forward_channels(original_dvb_forward_channel, dvb_fc)

    forward_channels.append(dvb_forward_channel)

    return {
        **original_window_parameters,
        "forward_channels": deepcopy(forward_channels),
    }


def gen_channel_config(row, directionality, original_channel_config):
    contact_overhead_time = "10s"

    original_class_annos = original_channel_config.get("classification_annotations", {})

    class_annos = None
    if original_class_annos:
        class_annos = gen_class_annos(row, original_class_annos)

    original_link_profile = original_channel_config["link_profile"]
    link_profile = gen_link_profile(row, directionality, original_link_profile)

    original_window_parameters = original_channel_config.get("window_parameters", {})

    window_parameters = gen_window_parameters(
        row, directionality, original_window_parameters
    )

    if window_parameters:
        assert (
            window_parameters["forward_channels"][0]["bandaid_override"]["pls"]
            == row.pls
        )

    original_dynamic_window_parameters = (
        original_channel_config.get("dynamic_window_parameters", {})
        .get("transmit_times", {})
        .get("elevation_threshold_deg", None)
    )
    dynamic_window_parameters = gen_dynamic_window_parameters(
        row, original_dynamic_window_parameters
    )

    return {
        **original_channel_config,
        "contact_overhead_time": contact_overhead_time,
        "link_profile": deepcopy(link_profile),
        **({"classification_annotations": class_annos} if class_annos else {}),
        **({"window_parameters": window_parameters} if window_parameters else {}),
        **(
            {"dynamic_window_parameters": dynamic_window_parameters}
            if dynamic_window_parameters
            else {}
        ),
    }


def fetch_data():
    connection = sql.connect(
        server_hostname="dbc-24e0a945-16d8.cloud.databricks.us",
        http_path="/sql/1.0/warehouses/c9cc905ac4a154ae",
        access_token=DATABRICKS_ACCESS_TOKEN,
    )

    cursor = connection.cursor()

    query = """
        SELECT *
        FROM ripley_dev.default.optimal_channel_properties
        WHERE gs_id = 'ubngs' and elevation < 70
        and spire_id in ('FM126', 'FM127', 'FM178', 'FM179', 'FM180', 'FM185', 'FM191', 'FM192')
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


# Finds already existing channels with the classification annotations that
# matches the markers.
# We will duplicate one of these channel and change it's PLS value.
def get_original_channel_ids(asset_id, directionality, row):
    channel_config_file = configs[asset_id]

    class_anno_markers = {
        "provider": "SPIRE",
        "directionality": directionality.name,
        "space_ground_uhf": directionality == Directionality.BIDIR,
        "ground_space_uhf": directionality == Directionality.BIDIR,
        "space_ground_sband": row.band == "S",
        "ground_space_sband": False,
        "space_ground_xband": row.band == "X",
        f"space_ground_{row.band.lower()}band_bandwidth_mhz": int(row.bw_mhz),
    }

    if row.band == "S":
        class_anno_markers["space_ground_sband_encoding"] = "DVBS2X"

    res = []

    for id, channel_config in channel_config_file.items():
        if not channel_config["enabled"]:
            continue

        class_annos = channel_config.get("classification_annotations", {})
        if all(
            class_annos.get(k, None) == v for k, v in class_anno_markers.items()
        ) and not class_annos.get("jira_ticket", "").startswith(JIRA_TICKET_ID):
            res.append(id)

    return res


def duplicate_channel_for_asset(asset_id, row, original_channel_id):
    original_channel_config = configs[asset_id][original_channel_id]

    assert original_channel_config["enabled"]

    new_channel_id = gen_channel_id(row, directionality)

    if asset_id not in new_configs:
        new_configs[asset_id] = {}

    assert new_channel_id not in new_configs[asset_id]

    new_configs[asset_id][new_channel_id] = deepcopy(
        gen_channel_config(row, directionality, original_channel_config)
    )

    print(f"Created new channel {new_channel_id} for {asset_id}")


def update_original_channel_ids(asset_id, channel_ids):
    if asset_id not in per_asset_original_channel_config_ids:
        per_asset_original_channel_config_ids[asset_id] = set()

    per_asset_original_channel_config_ids[
        asset_id
    ] = per_asset_original_channel_config_ids[asset_id].union(set(channel_ids))


parser = argparse.ArgumentParser()
parser.add_argument(
    "-e", "--environment", choices=["staging", "production"], required=True
)
parser.add_argument(
    "--gen-templates",
    help=f"Generate templates too",
    action="store_true",
    default=False,
)
args = parser.parse_args()

if not DATABRICKS_ACCESS_TOKEN:
    raise Exception("DATABRICKS_TOKEN environment variable is missing")

yaml = YAML()

configs = {}
new_configs = {}
old = {}

rows = fetch_data()

# Get rid of FMs that deorbited
rows = [
    row
    for row in rows
    if os.path.exists(asset_filepath(row.gs_id))
    and os.path.exists(asset_filepath(row.spire_id))
]

for r in rows:
    if not r.spire_id in configs:
        configs[r.spire_id] = load_config_file(r.spire_id)
    if not r.gs_id in configs:
        configs[r.gs_id] = load_config_file(r.gs_id)

per_asset_original_channel_config_ids = {}

for row in rows:
    gs_id = row.gs_id
    spire_id = row.spire_id

    if not gs_id in configs or not spire_id in configs:
        continue

    sat_config = configs[spire_id]
    gs_config = configs[gs_id]

    for directionality in [Directionality.TXO]:  # list(Directionality):
        print(
            f"\033[93mProcessing {gs_id} {spire_id} {row.band}-Band {row.bw_mhz}MHZ {row.pls}PLS {directionality.name}\033[00m"
        )

        original_channel_config_ids = get_original_channel_ids(
            gs_id, directionality, row
        )

        if not original_channel_config_ids:
            print(
                f"{gs_id} does not have any matching channels for {directionality.name}"
            )
            continue

        print(f"Found {len(original_channel_config_ids)} matching channels for {gs_id}")
        # print(original_channel_config_ids)

        original_channel_config_ids = [
            id
            for id in original_channel_config_ids
            if id in sat_config and sat_config[id]["enabled"]
        ]

        if not original_channel_config_ids:
            print(
                f"{spire_id} does not have any matching channels with {gs_id} for {directionality.name}"
            )
            continue

        print(
            f"Found {len(original_channel_config_ids)} shared channels between {gs_id} and {spire_id}"
        )

        update_original_channel_ids(gs_id, original_channel_config_ids)
        update_original_channel_ids(spire_id, original_channel_config_ids)

        original_config_id = original_channel_config_ids[0]

        print(f"Duplicating {original_config_id}")

        duplicate_channel_for_asset(gs_id, row, original_config_id)
        duplicate_channel_for_asset(spire_id, row, original_config_id)


for asset, cfg in new_configs.items():
    channel_tool(["delete", args.environment, asset, ",".join(cfg.keys()), "-y"])

    filename = asset_filepath(asset)
    with open(filename, "a") as file:
        yaml.dump(cfg, file)

    original_channels = per_asset_original_channel_config_ids[asset]

    assert original_channels

    if get_asset_type(asset) == "gs":
        asset_constraints_key = "ground_station_constraints"
        deny_key = "deny_satellites"
        edit_flag = "--ground_station_constraints_file"
    else:
        asset_constraints_key = "satellite_constraints"
        deny_key = "deny_ground_stations"
        edit_flag = "--satellite_constraints_file"

    denied_assets = deepcopy(cfg.get(asset_constraints_key, {}).get(deny_key, []))
    for other_asset in new_configs:
        if asset == other_asset:
            continue
        if get_asset_type(asset) == get_asset_type(other_asset):
            continue
        denied_assets.append(other_asset)

    asset_constraints = {deny_key: denied_assets}

    with open("/tmp/deny.yaml", "w") as file:
        yaml.dump(asset_constraints, file)

    channel_tool(
        [
            "edit",
            args.environment,
            asset,
            ",".join(original_channels),
            "-m",
            "merge",
            edit_flag,
            "/tmp/deny.yaml",
            "-y",
        ]
    )


summary = {k: [c for c in v] for k, v in new_configs.items()}
with open("/tmp/summary.yaml", "w") as file:
    yaml.dump(summary, file)

if args.gen_templates:
    for k in new_configs:
        cfg = new_configs[k]
        for ch, cf in cfg.items():
            cfg[ch]["enabled"] = False
            cfg[ch]["legal"] = False
        if get_asset_type(k) == "gs":
            with open("gs_templates.yaml", "a") as file:
                yaml.dump(cfg, file)
        else:
            with open("sat_templates.yaml", "a") as file:
                yaml.dump(cfg, file)

channel_tool(["normalize", args.environment, "all"])
channel_tool(["format"])
