#! /usr/bin/env python3

"""
Conversion script which processes NASA X-band missions from a CSV dump into channel config
constraint format. To use it:

    pipenv run python create_xband_constraints.py x_band_moa_constraints.csv \
        > fragments/x_band_coordination.yaml

The latest coordination agreements can be found here:

https://drive.google.com/drive/folders/14D0VWBnQTpAEljVNZmfVwnS-ss276iMy

To convert the table to CSV, copy and paste it into a new Sheets document and export from there. You
may need to adjust the column headers, or merge columns, to get the right format. This script
expects the following columns to exist:

    Agency,Mission,Rx ES Location,Lat (N),Long (E),NORAD ID,Launch Date/Status

The formatted YAML constraints are printed to stdout.
"""

import csv
import sys
from collections import defaultdict

from ruamel.yaml import YAML, comments

yaml = YAML()

TOPLEVEL_COMMENT = """X-band constraints to comply with NASA/Spire coordination agreement

https://docs.google.com/document/d/1zSxW1yMJnskzFpVrb3STgVL-6T8JZY2L/edit 

Appendix A contains a list of protected missions, their NORAD IDs, and their ground station
coordinates. We need to avoid transmitting when our satellites are in the beam between one of the
protected satellites and its ground station. Only launched missions are included here."""

# NASA has provided some bad IDs; this maps them to the corrected version.
NORAD_ID_CORRECTIONS = {49620: 49260, 42069: 42063}

# These missions are now listed as "dead" in Celestrak.
EOL_MISSIONS = {
    20436,  # SPOT-2
    25260,  # SPOT-4
    27421,  # SPOT-5
}


def main(file_name):
    with open(file_name, "r") as f:
        reader = csv.DictReader(f)
        missions = aggregate_by_mission(reader)
        missions = combine_similar_missions(missions)
        constraints = to_constraints(missions)
        toplevel = comments.CommentedMap()
        toplevel.yaml_set_start_comment(TOPLEVEL_COMMENT)
        toplevel["separation"] = constraints
        yaml.dump(toplevel, sys.stdout)


def new_mission():
    return defaultdict(set)


def aggregate_by_mission(rows):
    missions = defaultdict(new_mission)
    for row in rows:
        if row["Launch Date/Status"] != "In orbit":
            continue

        norad_id = int(row["NORAD ID"])
        if norad_id in NORAD_ID_CORRECTIONS:
            norad_id = NORAD_ID_CORRECTIONS[norad_id]

        if norad_id in EOL_MISSIONS:
            continue

        mission = row["Agency"] + ": " + row["Mission"]
        missions[mission]["NORAD IDs"].add(norad_id)
        missions[mission]["Stations"].add(
            (row["Rx ES Location"], float(row["Lat (N)"]), float(row["Long (E)"]))
        )

    return missions


def combine_similar_missions(missions):
    missions_by_stations = {}
    for mission, assets in missions.items():
        stations = frozenset(assets["Stations"])
        entry = missions_by_stations.get(stations)
        if not entry:
            missions_by_stations[stations] = {
                "missions": mission,
                "norad_ids": assets["NORAD IDs"],
            }
        else:
            entry["missions"] += ", " + mission
            entry["norad_ids"].update(assets["NORAD IDs"])
    return {
        v["missions"]: {"NORAD IDs": v["norad_ids"], "Stations": k}
        for k, v in missions_by_stations.items()
    }


def to_constraints(missions):
    constraints = []
    # Sort by first mission in the set here so that the diff will stay nice-ish if the input changes
    for (mission, assets) in sorted(missions.items(), key=lambda kv: kv[0]):
        constraint = comments.CommentedMap()
        constraint.yaml_add_eol_comment(mission, "norad_ids")
        constraint["type"] = "avoid_ground_station_beams"
        constraint["norad_ids"] = sorted(assets["NORAD IDs"])

        def to_gs_entry(loc, lat, lon):
            entry = comments.CommentedMap()
            entry.yaml_add_eol_comment(loc, "latitude")
            entry["latitude"] = lat
            entry["longitude"] = lon
            entry["elevation_m"] = 0.0
            return entry

        constraint["station_coordinates"] = [
            # Sort by location name to keep the diff clean
            to_gs_entry(*gs)
            for gs in sorted(assets["Stations"], key=lambda vs: vs[0])
        ]
        constraint["beamwidth_deg"] = 5
        constraints.append(constraint)

    return constraints


if __name__ == "__main__":
    main(sys.argv[1])
