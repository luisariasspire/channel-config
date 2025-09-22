# This script can populate per-pair elevation fields in link
# profiles based on data it fetches from Databricks (requires
# an ECT Databricks access token).
#
# This will be the ancestor of the eventual channel tool command to do
# this. Since it's temporary, correctness is the only priority.
#
# This script takes the PLS picker step, and using and optimizing
# function uses the 3 spread (low, medium and high)
# PLS values that maximize bandidth while minimizing elevation

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from datetime import datetime

import numpy as np
import requests
from ruamel.yaml import YAML
from scipy.optimize import linprog

if __name__ != "__main__":
    sys.exit("do not import this script")

# Constants

DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_SERVER_HOSTNAME = os.getenv(
    "DATABRICKS_SERVER_HOSTNAME",
    "https://dbc-24e0a945-16d8.cloud.databricks.us"
)
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "c9cc905ac4a154ae")


abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

class Directionality(Enum):
    TXO = 1
    BIDIR = 2


BITRATE_SCALE_FACTOR = 0.9

command_history = {}

yaml = YAML()

@dataclass
class ChannelConfig:
    sat_count: int
    mbps: float
    pls: float
    elevation: float
    category: str


def fetch_data(query: str) -> Optional[List[namedtuple]]:
    """Fetch data from Databricks using SQL query.

    Args:
        query: SQL query string to execute

    Returns:
        List of namedtuples containing query results

    Raises:
        requests.exceptions.HTTPError: If API request fails
    """
    HEADERS = {
        "Authorization": f"Bearer {DATABRICKS_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # --- Step 1: Submit the query ---
    submit_url = f"{DATABRICKS_SERVER_HOSTNAME}/api/2.0/sql/statements"
    payload = {
        "catalog": "ripley_dev",
        "schema": "default",
        "statement": query,
        "warehouse_id": WAREHOUSE_ID
    }

    response = requests.post(submit_url, headers=HEADERS, json=payload)
    response.raise_for_status()

    data = response.json()
    statement_id = data["statement_id"]

    # --- Step 2: Poll for completion ---
    status_url = f"{DATABRICKS_SERVER_HOSTNAME}/api/2.0/sql/statements/{statement_id}"

    while True:
        status_response = requests.get(status_url, headers=HEADERS)
        status_response.raise_for_status()
        status_data = status_response.json()

        state = status_data["status"]["state"]

        if state in ("SUCCEEDED", "FAILED", "CANCELED"):
            if "status" in status_data and "error" in status_data["status"] and "message" in status_data["status"][
                "error"]:
                print("Error: " + status_data["status"]["error"]["message"])
            break
        time.sleep(2)

    # --- Step 3: Handle result ---
    if state == "SUCCEEDED":
        result_data = status_data["result"]

        if "data_array" in result_data:
            data = []
            columns = {c["name"]: c["type_name"] for c in status_data["manifest"]["schema"]["columns"]}
            def parse_value(v, c):
                if v is None:
                    return v
                if c == "STRING":
                    return v
                elif c == "TIMESTAMP":
                    return datetime.fromisoformat(v)
                else:
                    return json.loads(v)

            for row in result_data["data_array"]:
                values = {k:parse_value(v, columns[k]) for k, v in zip(columns.keys(), row)}
                data.append(namedtuple('row', columns)(**values))

            return data
    else:
        print(f"\nQuery failed or canceled. State: {state}")


def categorize_pls(pls):
    """Categorize pls into low, medium, high by tertiles"""
    sorted_pls = sorted(pls)
    low_thresh = sorted_pls[len(pls)//3]
    high_thresh = sorted_pls[2*len(pls)//3]

    categories = []
    for p in pls:
        if p <= low_thresh:
            categories.append("low")
        elif p >= high_thresh:
            categories.append("high")
        else:
            categories.append("medium")
    return categories


def optimize_link(sat_count: list[int], mbps: list[float], pls: list[float], elevation: list[float]) -> dict:
    n = len(sat_count)

    # Objective: maximize sat_count + mbps, minimize elevation
    c = -np.array(sat_count) - np.array(mbps) + np.array(elevation)

    # Categorize pls
    categories = categorize_pls(pls)
    cats = ["low", "medium", "high"]

    # Constraints: select 1 option per category
    A_eq = []
    b_eq = []
    for cat in cats:
        row = [1 if categories[i] == cat else 0 for i in range(n)]
        A_eq.append(row)
        b_eq.append(1)

    # Bounds: x[i] ∈ [0,1]
    bounds = [(0, 1) for _ in range(n)]

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if res.success:
        chosen_indices = [i for i, val in enumerate(res.x) if val > 1e-6]
        return {
            "chosen_pls": [pls[i] for i in chosen_indices],
            "solutions": [
                ChannelConfig(
                    sat_count=sat_count[i],
                    mbps=mbps[i],
                    pls=pls[i],
                    elevation=elevation[i],
                    category=categories[i]
                )
                for i in chosen_indices
            ]
        }
    else:
        raise ValueError("Optimization failed: " + res.message)


def pls_picker(gs_ids: list[str], band: str = "S"):
    """Fetch PLS (Physical Layer Signaling) values and associated data from Databricks.

    Args:
        gs_ids: List of ground station IDs to query
        band: Frequency band to query (defaults to "S")

    Returns:
        List of namedtuples containing PLS values and associated metrics for each ground station
    """
    gs_ids = "'" + "', '".join(gs_ids) + "'"
    query = f"""
       with aq as (
          select gs_id, collect_set(spire_id) as satellites,
            pls, cardinality(collect_set(spire_id)) * round(elevation) as elev_sum,
            bw_mhz, band, any_value(mbps) as mbps
          from
            optimal_channel_properties
          where
            gs_id in ({ gs_ids }) and band in ('{ band }') and elevation < 70
          group by gs_id, pls, round(elevation), bw_mhz, band
        )
        select
          aq.gs_id,
          sum(cardinality(aq.satellites)) as sat_count,
          round(sum(elev_sum) / sum(cardinality(aq.satellites))) as elevation,
          aq.pls,
          aq.bw_mhz,
          aq.band,
          aq.mbps,
          coalesce(round(gs.elevation), 90) as default_min_elevation_deg
        from
          aq
            left join optimal_channel_properties_gs gs
              on aq.gs_id = gs.gs_id
              and aq.pls = gs.pls
              and aq.bw_mhz = gs.bw_mhz
              and aq.band = gs.band
        group by 
          aq.gs_id,
          aq.pls,
          aq.bw_mhz,
          aq.band,
          aq.mbps,
          gs.elevation
        order by
          sat_count desc,
          pls asc;
    """
    pls_values = fetch_data(query)
    return pls_values


def get_new_channels(gs_id, pls:list[int], band:str="S"):
    """Get channel configurations for specified PLS values and ground station.

    Args:
        gs_id: Ground station ID to query
        pls: List of PLS values to fetch channels for 
        band: Frequency band (defaults to "S")

    Returns:
        List of namedtuples containing channel configurations including satellite elevations
    """
    pls = ','.join([str(p) for p in pls])
    query = f"""
        with aq as (
            select
                gs_id,  pls, bw_mhz, band, 
                collect_set(spire_id) as satellites,
                round(elevation) as min_elevation_deg,                 
                any_value(mbps) as mbps
            from ripley_dev.default.optimal_channel_properties
            where 
                gs_id = "{gs_id}" and band = '{band}' and pls in ({pls})
            group by gs_id, pls, round(elevation), bw_mhz, band
        )
        select 
            aq.gs_id, aq.pls, aq.bw_mhz, aq.band, aq.mbps,
            collect_list(
                struct(cast(aq.min_elevation_deg as int) as min_elevation_deg, aq.satellites)
            ) as satellite_min_elevations,
            coalesce(round(gs.elevation), 90) as default_min_elevation_deg
        from aq
                 left join ripley_dev.default.optimal_channel_properties_gs gs 
                 on aq.gs_id = gs.gs_id and aq.pls = gs.pls and aq.bw_mhz = gs.bw_mhz and aq.band = gs.band
        group by aq.gs_id, aq.pls, aq.bw_mhz, aq.band, aq.mbps, gs.elevation
    """
    new_channels = fetch_data(query)

    return new_channels


def get_optimized_channel(gs_id:str=None, band:str="S"):
    """Get optimized channel configuration for a ground station.

    Fetches PLS values, optimizes selection based on metrics, and retrieves full channel config.

    Args:
        gs_id: Ground station ID to optimize channel for
        band: Frequency band (defaults to "S")

    Returns:
        Optimized channel configuration for the ground station
    """
    pls_values = pls_picker(gs_ids=[gs_id], band=band)
    if pls_values is None:
        print(f"No PLS values found for ground station {gs_id}.")
        return None

    print(f"{gs_id} has the possible PLS values: ")
    for r in pls_values:
        print(f"sat_count: {r.sat_count}, elevation: {r.elevation}, pls: {r.pls}, mbps: {r.mbps}")

    sat_count = [r.sat_count for r in pls_values]
    mbps = [r.mbps for r in pls_values]
    pls = [r.pls for r in pls_values]
    elevation = [r.elevation for r in pls_values]

    optimized = optimize_link(sat_count, mbps, pls, elevation)
    print("Got optimized values: " + str(optimized["chosen_pls"]))

    new_channels = get_new_channels(gs_id=gs_id, pls=optimized["chosen_pls"], band=band)
    return new_channels


def get_optimized_channels(gs:list[str]=(), band: str = "S"):
    """Get optimized channel configurations for one or all ground stations.

    Args:
        gs_id: Optional ground station ID. If None, optimizes all ground stations
        band: Frequency band (defaults to "S")
    """
    if len(gs) == 0:
        gs = fetch_data("select gs_id, sband_enabled, sband_only "
                        "from tk_catalog.public.groundstations "
                        "where `group` = 'thewild'")
        if band.upper() == "S":
            gs = [g.gs_id for g in gs if g.sband_enabled]
        else:
            gs = [g.gs_id for g in gs if not g.sband_only]

    print("Getting channels for ground stations: " + str(gs))

    optimized_channels = []
    for gs_id in gs:
        optimized_channel = get_optimized_channel(gs_id, band)
        if optimized_channel is not None:
            optimized_channels.append((gs_id, optimized_channel))
    return optimized_channels


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


def get_asset_type(asset_id):
    """Determine if an asset ID represents a satellite or ground station.

    Args:
        asset_id: Asset identifier to check

    Returns:
        "sat" for satellites (FM*), "gs" for ground stations
    """
    regex = re.compile("^FM.*$")
    if regex.match(asset_id):
        return "sat"
    else:
        return "gs"


def asset_filepath(asset_id):
    """Get the configuration file path for an asset.

    Args:
        asset_id: Asset identifier

    Returns:
        Path to the asset's YAML configuration file
    """
    asset_type = get_asset_type(asset_id)

    return f"{args.environment}/{asset_type}/{asset_id}.yaml"


def load_config_file(asset_id):
    """Load YAML configuration for an asset.

    Args:
        asset_id: Asset identifier

    Returns:
        Parsed YAML configuration dictionary
    """
    filename = asset_filepath(asset_id)

    with open(filename, "r") as file:
        try:
            channel_config_file = yaml.load(file)
        except Exception as _:
            print(f"Failed to load {filename}")
            return

    return channel_config_file


def get_channel_link_profile(gs_id, predicate):
    """Get link profiles matching a predicate for a ground station.

    Args:
        gs_id: Ground station ID
        predicate: Query predicate to filter channels

    Returns:
        List of tuples containing (channel_id, link_profile) pairs
    """
    channels = channel_tool(
        ["query", args.environment, gs_id, predicate, "link_profile"], sync=True
    )

    decoded = channels.decode("utf-8")
    result = decoded.splitlines()[1:]

    link_profiles = []
    for profile in result:
        fields = profile.split(",", maxsplit=2)

        assert fields[0] == gs_id

        link_profile = (fields[1], yaml.load(fields[2]))
        link_profiles.append(link_profile)
    return link_profiles


def get_active_assets():
    return fetch_data("""
     SELECT
         spire_id AS asset_id
     FROM tk_catalog.public.satellites
     WHERE spire_id LIKE 'FM%'
       AND support_stage IN ('production', 'checkout_commissioning')
     """)


def run_channels(new_channels):
    # We get a list of pls values from databricks but for various reasons we may not
    # process them. e.g. if all the assets under that pls value are decommisioned.
    # So let's keep track of what we processed.
    new_pls_values = {}

    for row in new_channels:
        # skip if the gs is decomissioned
        if not os.path.exists(asset_filepath(row.gs_id)):
            print(f"Skipping {row.gs_id} due to missing configuration file.")
            continue

        gs_id = row.gs_id
        pls = row.pls
        bw_mhz = row.bw_mhz
        band = row.band.lower()
        downlink_rate_kbps = row.mbps * 1000 * BITRATE_SCALE_FACTOR
        satellite_min_elevations = row.satellite_min_elevations
        for min_elevations in row.satellite_min_elevations:
            min_elevations["min_elevation_deg"] = int(min_elevations["min_elevation_deg"])

        default_min_elevation_deg = int(row.default_min_elevation_deg)

        configs = load_config_file(gs_id)
        if configs is None:
            continue
        config_values = [c for c in list(configs.values()) if isinstance(c, dict) and "classification_annotations" in c]
        mid_freq = (
            2200.5
            if any(
                c["classification_annotations"].get("space_ground_sband", None)
                and c["classification_annotations"].get("space_ground_sband_mid_freq_mhz", None) == 2200.5
                for c in config_values
            )
            else 2022.5
        )
        supports_bidir = any(
            c["classification_annotations"].get("directionality", None) == "BIDIR"
            and c["enabled"]
            and c["legal"]
            for c in config_values
        )

        supported_directionality = [Directionality.TXO]
        if supports_bidir:
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
                for sat in get_active_assets()
                if all(
                    sat.asset_id not in d["satellites"] for d in satellite_min_elevations
                )
            ]

            for entry in satellite_min_elevations:
                if entry["min_elevation_deg"] == 90.0:
                    entry["satellites"].extend(disabled_sats)
                    break
            else:
                satellite_min_elevations.append(
                    {"min_elevation_deg": 90.0, "satellites": disabled_sats}
                )

            predicate = (
                f"directionality == '{directionality.name}' and "
                "provider == 'SPIRE' and "
                f"space_ground_{band}band_bandwidth_mhz == {bw_mhz} and "
                "(space_ground_xband or space_ground_sband_encoding == 'DVBS2X') and "
                f"(not space_ground_sband_mid_freq_mhz or space_ground_sband_mid_freq_mhz == {mid_freq})"
            )

            comma_separated_assets = (
                    ",".join(
                        ",".join(d["satellites"])
                        for d in satellite_min_elevations
                        # Make sure we don't create a channel for disabled sats
                        # They're disabled to ensure we don't communicate with this groundstation
                        # if the sat gets the channel by some other means in the future.
                        if d["min_elevation_deg"] != 90.0
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
            for (channel_id, link_profile) in get_channel_link_profile(gs_id, edit_predicate):

                dvb_link_profile = max(link_profile, key=lambda i: i["downlink_rate_kbps"])
                dvb_link_profile["satellite_min_elevations"] = satellite_min_elevations

                config_file = load_config_file(gs_id)
                if config_file is None:
                    continue
                if "dynamic_window_parameters" in config_file[channel_id]:
                    dvb_link_profile["add_transmit_times"] = True
                    subprocess.run(
                        [
                            "yq",
                            "-i",
                            "-y",
                            f"del(.{channel_id}.dynamic_window_parameters)",
                            asset_filepath(gs_id),
                        ],
                    )
                    subprocess.run(
                        [
                            "yq",
                            "-i",
                            "-y",
                            f"del(.{channel_id}.dynamic_window_parameters)",
                            "gs_templates.yaml",
                        ]
                    )

                # if we duplicated a channel that uses the old key, replace it.
                if dvb_link_profile.pop("min_elevation_deg", None):
                    dvb_link_profile["default_min_elevation_deg"] = default_min_elevation_deg

                lp = [dict(dvb_link_profile)]

                if directionality == Directionality.BIDIR and band == "s":
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



parser = argparse.ArgumentParser()
parser.add_argument(
    "-e", "--environment", choices=["staging", "production"], required=True
)
parser.add_argument(
    "-b", "--bands", choices=["X", "S", "both"], required=False, default="both"
)
parser.add_argument(
    "-g", "--gs_ids", required=False, default=""
)
args = parser.parse_args()


if not DATABRICKS_ACCESS_TOKEN:
    raise Exception("DATABRICKS_TOKEN environment variable is missing")


bands = ["S", "X"] if args.bands.lower() == "both" else [args.bands]
print(f"Running for band(s) {bands}")
for band in bands:
    gs_ids = [g for g in args.gs_ids.split(",") if g != '']
    for (gs_id, new_channels) in get_optimized_channels(gs=gs_ids, band=band):
        print(f"Optimizing {gs_id}")
        run_channels(new_channels)