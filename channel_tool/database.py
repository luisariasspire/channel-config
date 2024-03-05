"""Prototype schema for representing the Channel Config data in a relational database."""

import json
import os
import sqlite3
from collections import defaultdict
from typing import Any, DefaultDict, List, Mapping, Optional
from uuid import UUID, uuid4

from ruamel.yaml import YAML

from channel_tool.asset_config import infer_asset_type, load_asset_config, locate_assets
from channel_tool.typedefs import AssetConfig, ChannelDefinition, Environment
from channel_tool.util import GROUND_STATION, SATELLITE, dump_yaml_string

yaml = YAML()
with open("contact_type_defs.yaml") as f:
    y = yaml.load(f)
    CHANNEL_DEFS = y["contact_types"]
    BAND_DEFS = y["bands"]

with open("sat_license_defs.yaml") as f:
    y = yaml.load(f)
    SAT_LICENSE_DEFS = y["sat_licenses"]
    GS_LICENSE_DEFS = y["gs_licenses"]
    ALL_ISO_COUNTRIES = y["definitions"]["all_iso_countries"]
    SPIRE_COUNTRIES = y["definitions"]["spire_gs_countries"]
    SPIRE_ID_OVERRIDES = y["definitions"]["spire_id_overrides"]


ICEGS_LICENSE_ID = uuid4()
ICEGS_BANDS = [
    {
        "id": "SBAND_2200_5_D",
        "band": [2200, 2201],
        "space_to_earth": True,
        "earth_to_space": False,
    },
    {
        "id": "SBAND_2032_5_U",
        "band": [2030, 2035],
        "space_to_earth": False,
        "earth_to_space": True,
    },
    {
        "id": "XBAND8200_D",
        "band": [8170, 8230],
        "space_to_earth": True,
        "earth_to_space": False,
    },
]

LUX_MINAS_USMA_LICENSE_ID = uuid4()
LUX_MINAS_BANDS = [
    {
        "id": "UHF402_7_UD",
        "band": [402.6, 402.8],
        "space_to_earth": True,
        "earth_to_space": True,
    },
    {
        "id": "UHF_402_7_D",
        "band": [
            402.6,
            402.8,
        ],
        "space_to_earth": True,
        "earth_to_space": False,
    },
    {
        "id": "UHF_402_7_U",
        "band": [
            402.6,
            402.8,
        ],
        "space_to_earth": False,
        "earth_to_space": True,
    },
    {
        "id": "UHF_450_U",
        "band": [
            449.75,
            450.25,
        ],
        "space_to_earth": False,
        "earth_to_space": True,
    },
    {
        "id": "SBAND_2022_5_D",
        "band": [
            2020,
            2025,
        ],
        "space_to_earth": True,
        "earth_to_space": False,
    },
    {
        "id": "SBAND_2032_5_U",
        "band": [
            2030,
            2035,
        ],
        "space_to_earth": False,
        "earth_to_space": True,
    },
    # NOTE: For testing, remove this license from LUX so ICEGS has a frequency the satellite doesn't
    #  {
    #  "id": "SBAND_2200_5_D",
    #  "band": [
    #  2200,
    #  2201,
    #  ],
    #  "space_to_earth": True,
    #  "earth_to_space": False,
    #  },
    {
        "id": "XBAND8200_D",
        "band": [
            8170,
            8230,
        ],
        "space_to_earth": True,
        "earth_to_space": False,
    },
]
UNLICENSED_BANDS = [
    {
        "id": "UNLICENSED_BAND",
        "band": [
            10000,
            20000,
        ],
        "space_to_earth": True,
        "earth_to_space": True,
    },
]

ALL_BANDS = ICEGS_BANDS + LUX_MINAS_BANDS + UNLICENSED_BANDS


def license(license_def: Mapping[str, Any]) -> str:
    desc = license_def.get("description")
    if desc:
        desc = f"'{desc}'"
    else:
        desc = "NULL"

    return f"""INSERT OR IGNORE INTO License VALUES (
        '{license_def["id"]}',
        {desc}
    );"""


def frequency_band(band_def: Mapping[str, Any]) -> str:
    return f"""
    INSERT OR IGNORE INTO FrequencyBand VALUES (
    '{band_def["id"]}',
    {band_def["band"][0]},
    {band_def["band"][1]},
    {band_def["space_to_earth"]},
    {band_def["earth_to_space"]}
    );
    """


def licensed_frequency(
    license_id: UUID, band_id: Any, allowed_countries: Any = {}
) -> str:
    return f"""
    INSERT INTO LicensedFrequency VALUES (
    '{license_id}',
    '{band_id}',
    '{json.dumps(allowed_countries)}'
    );
    """


def asset(asset_id: str, asset_type: str, license_id: str) -> str:
    return f"INSERT INTO Asset VALUES ('{asset_id}', '{asset_type}', '{license_id}');"


CHANNELS = [
    {
        "id": "CONTACT_BIDIR",
        "desc": "Bidirectional contact with UHF up and S-band down",
        "contact_type": "CONTACT_BIDIR",
        "directionality": "Bidirectional",
        "frequencies": ["UHF402_7_UD", "SBAND_2022_5_D"],
    },
    {
        "id": "CONTACT_RXO",
        "desc": "One-way contact with S-band down",
        "contact_type": "CONTACT_RXO",
        "directionality": "SpaceToGround",
        "frequencies": ["SBAND_2022_5_D"],
    },
    {
        "id": "CONTACT_RXO_SBAND_FREQ_2200_MHZ",
        "desc": "One-way contact with S-band down in 2200-2201 MHz band",
        "contact_type": "CONTACT_RXO_SBAND_FREQ_2200_MHZ",
        "directionality": "SpaceToGround",
        "frequencies": ["SBAND_2200_5_D"],
    },
    {
        "id": "TXO_XBAND",
        "desc": "One-way contact with X-band down",
        "contact_type": "CONTACT_SPACE_GROUND_TXO",
        "directionality": "SpaceToGround",
        "frequencies": ["XBAND8200_D"],
    },
    {
        "id": "ILLEGAL_CONTACT",
        "desc": "Illegal contact that requires an unlicensed band",
        "contact_type": "CONTACT_ILLEGAL",
        "directionality": "Bidirectional",
        "frequencies": ["UNLICENSED_BAND"],
    },
    {
        "id": "KIND_OF_ILLEGAL_CONTACT",
        "desc": "Illegal contact that requires an unlicensed band, as well as a licensed one",
        "contact_type": "CONTACT_KINDA_ILLEGAL",
        "directionality": "Bidirectional",
        "frequencies": ["UNLICENSED_BAND", "SBAND_2200_5_D"],
    },
]


def channel(channel_def: Mapping[str, Any]) -> str:
    return f"""
    INSERT INTO Channel VALUES (
    '{channel_def["id"]}',
    '{channel_def["desc"]}',
    '{channel_def["contact_type"]}',
    '{channel_def["directionality"]}'
    )
    """


def channel_frequency(channel_id: str, band_id: str) -> str:
    return f"""
        INSERT INTO ChannelFrequency VALUES (
        '{channel_id}',
        '{band_id}'
        )
        """


def channel_frequencies(channel_def: Mapping[str, Any]) -> List[str]:
    return [
        channel_frequency(channel_def["id"], freq)
        for freq in channel_def["frequencies"]
    ]


CHANNEL_FREQUENCY_ASSIGNMENTS = []

for c in CHANNELS:
    CHANNEL_FREQUENCY_ASSIGNMENTS.extend(channel_frequencies(c))


def asset_channel_config(
    asset_id: str,
    channel_id: str,
    link_profile: Optional[str] = None,
    parameter_set: Optional[str] = None,
    enabled: bool = True,
) -> str:
    lp = f"'{link_profile}'" if link_profile else "NULL"
    ps = f"'{parameter_set}'" if parameter_set else "NULL"

    return f"""
    INSERT OR REPLACE INTO AssetChannelConfig VALUES (
    '{asset_id}',
    '{channel_id}',
    {enabled},
    {lp},
    {ps}
    )
    """


def link_profile(id: str, profile: Any, contact_overhead_time: Any) -> str:
    return f"""
    INSERT OR REPLACE INTO LinkProfile VALUES (
    '{id}',
    '{json.dumps(profile)}',
    '{contact_overhead_time}'
    )
    """


def parameter_set(id: str, params: Any) -> str:
    return f"""
    INSERT OR REPLACE INTO ParameterSet VALUES (
    '{id}',
    '{json.dumps(params)}'
    )
    """


def constraint_definition(id: str, kind: str, definition: Any) -> str:
    return f"""
    INSERT OR REPLACE INTO ConstraintDefinition VALUES (
    '{id}',
    '{kind}',
    '(No description)',
    '{json.dumps(definition)}'
    )
    """


def operational_constraint(asset_id: str, channel_id: str, constraint_id: str) -> str:
    return f"""
    INSERT OR REPLACE INTO OperationalConstraint VALUES (
    '{asset_id}',
    '{channel_id}',
    '{constraint_id}'
    )
    """


SCHEMA = [
    "PRAGMA foreign_keys = ON;",
    # Frequency bands are allowed by licenses and required by channels.
    # TODO Could we consolidate the two booleans with a Directionality?
    """CREATE TABLE FrequencyBand(
        id PRIMARY KEY,
        low_mhz,
        high_mhz,
        space_to_earth,
        earth_to_space
    );""",
    # Radiofrequency licenses such as the LUX MINAS license or KSAT's license.
    "CREATE TABLE License(id PRIMARY KEY, description);",
    # Decomposed relation for the specific frequencies used in a particular license.
    """CREATE TABLE LicensedFrequency(
        license_id,
        band_id,
        allowed_countries,
        PRIMARY KEY(license_id, band_id),
        FOREIGN KEY(license_id) REFERENCES License(id),
        FOREIGN KEY(band_id) REFERENCES FrequencyBand(id)
    );""",
    # Channels are independent of ground stations and satellites.
    # TODO Add default parameters and link profile
    "CREATE TABLE Channel(id PRIMARY KEY, description, contact_type, direction);",
    # Channels require 1 or more frequencies.
    """CREATE TABLE ChannelFrequency(
        channel_id,
        band_id,
        PRIMARY KEY(channel_id, band_id),
        FOREIGN KEY(channel_id) REFERENCES Channel(id),
        FOREIGN KEY(band_id) REFERENCES FrequencyBand(id)
    );""",
    # Assets are ground stations or satellites. They have a single license.
    """CREATE TABLE Asset(
        id PRIMARY KEY,
        kind,
        license_id,
        FOREIGN KEY(license_id) REFERENCES License(id)
    );""",
    # Link profiles indicate the expected performance characteristics of a contact.
    # Factor them out so that we can reuse profiles and adjust them across the fleet.
    """CREATE TABLE LinkProfile(
    id PRIMARY KEY,
    profile,
    overhead_time
    );
    """,
    # Parameter sets specify the settings required for the various components in the RF chain.
    # Again, factor them out for reuse.
    """CREATE TABLE ParameterSet(
    id PRIMARY KEY,
    parameters
    );
    """,
    # For each asset and each channel, we can have a config which says if it's enabled or not, what
    # parameters to use, and what the link profile is.
    """CREATE TABLE AssetChannelConfig(
        asset_id,
        channel_id,
        enabled,
        link_profile_id,
        parameter_set_id,
        PRIMARY KEY(asset_id, channel_id),
        FOREIGN KEY(asset_id) REFERENCES Asset(id),
        FOREIGN KEY(channel_id) REFERENCES Channel(id),
        FOREIGN KEY(link_profile_id) REFERENCES LinkProfile(id),
        FOREIGN KEY(parameter_set_id) REFERENCES ParameterSet(id)
    );""",
    # Constraint definitions are rules and restrictions on when a channel can be used. These are
    # given in JSON or YAML format and are used to direct the Contact Scheduler.
    """CREATE TABLE ConstraintDefinition(
        id PRIMARY KEY,
        kind,
        description,
        rule
    );
    """,
    # Operational constraints map constraint definitions to a specific asset/channel combination.
    # Multiple constraints can be added to each asset/channel pair, so these are not part of the
    # AssetChannelConfig. Note: CONSTRAINT is a SQL reserved keyword so we use "rule" instead.
    #
    # TODO Add DB constraint requiring asset kind and constraint kind to match
    """CREATE TABLE OperationalConstraint(
        asset_id,
        channel_id,
        rule_id,
        PRIMARY KEY(asset_id, channel_id, rule_id),
        FOREIGN KEY(asset_id) REFERENCES Asset(id),
        FOREIGN KEY(channel_id) REFERENCES Channel(id),
        FOREIGN KEY(rule_id) REFERENCES ConstraintDefinition(id)
    );
    """,
]

SAMPLE_DATA_SCHEMA = [
    f"INSERT INTO License VALUES ('{ICEGS_LICENSE_ID}', 'Norwegian ground station license');",
    f"INSERT INTO License VALUES ('{LUX_MINAS_USMA_LICENSE_ID}', 'Luxembourg MINAS with US Market Access');",
    *[frequency_band(b) for b in ALL_BANDS],
    f"INSERT INTO Asset VALUES ('icegs', 'ground_station', '{ICEGS_LICENSE_ID}');",
    f"INSERT INTO Asset VALUES ('FM100', 'satellite', '{LUX_MINAS_USMA_LICENSE_ID}');",
    *[licensed_frequency(LUX_MINAS_USMA_LICENSE_ID, b["id"]) for b in LUX_MINAS_BANDS],
    *[licensed_frequency(ICEGS_LICENSE_ID, b["id"]) for b in ICEGS_BANDS],
    *[channel(c) for c in CHANNELS],
    *CHANNEL_FREQUENCY_ASSIGNMENTS,
    asset_channel_config("icegs", "TXO_XBAND"),
    asset_channel_config("icegs", "CONTACT_RXO", enabled=False),
    asset_channel_config("FM100", "TXO_XBAND"),
    asset_channel_config("FM100", "CONTACT_RXO", enabled=True),
]


def _run_statements(stmts: List[str]) -> None:
    con = sqlite3.connect("channels.db")
    cur = con.cursor()
    for line in stmts:
        try:
            cur.execute(line)
            con.commit()
        except Exception as e:
            print("Failed to execute SQL statement:\n", line)
            raise e


def init() -> None:
    # Start from a clean slate.
    try:
        os.remove("channels.db")
    except FileNotFoundError:
        pass
    _run_statements(SCHEMA)


def load_sample_data() -> None:
    _run_statements(SAMPLE_DATA_SCHEMA)


def _create_frequency_bands() -> None:
    defs = []

    for id, band_info in BAND_DEFS.items():
        defs.append(frequency_band({"id": id, **band_info}))

    _run_statements(defs)


def allows_use(licensed_freqs: List[Any], band_def: Mapping[str, Any]) -> bool:
    """Test if a license allows use of a channel, based on its required frequency bands."""

    def has_matching_freq(band_low: Any, band_high: Any, band_dir: Any) -> bool:
        for freq in licensed_freqs:
            lic_low = freq[0]
            lic_high = freq[1]
            lic_dir = freq[2]
            if lic_low <= band_low and band_high <= lic_high and band_dir == lic_dir:
                return True
        return False

    def is_allowed(band: Mapping[str, Any]) -> bool:
        band_low = band["band"][0]
        band_high = band["band"][1]
        if band["earth_to_space"] and not has_matching_freq(band_low, band_high, "U"):
            return False
        if band["space_to_earth"] and not has_matching_freq(band_low, band_high, "D"):
            return False
        return True

    if "any_of" in band_def:
        for b in band_def["any_of"]:
            if is_allowed(b):
                return True
        return False
    else:
        return is_allowed(band_def)


def _create_licenses() -> None:
    defs = []

    for id, license_info in SAT_LICENSE_DEFS.items():
        defs.append(license({"id": id, **license_info}))

    for lid, license_info in SAT_LICENSE_DEFS.items():
        for bid, band_info in BAND_DEFS.items():
            if allows_use(license_info["frequencies"], band_info):
                allowed_countries = [
                    c
                    for c in SPIRE_COUNTRIES
                    if c not in license_info["blacklisted_countries"]
                ]
                defs.append(licensed_frequency(lid, bid, allowed_countries))

    stations: DefaultDict[str, Any] = defaultdict(lambda: defaultdict(list))
    for band, countries in GS_LICENSE_DEFS.items():
        for country, allowed_stations in countries.items():
            for station in allowed_stations:
                stations[station][band].append(country)

    for station, bands in stations.items():
        lid = f"{station}_gs_license"
        defs.append(
            license({"id": lid, "description": f"Ground station license for {station}"})
        )
        for bid, allowed_countries in bands.items():
            defs.append(licensed_frequency(lid, bid, allowed_countries))

    _run_statements(defs)


def _create_satellites() -> None:
    defs = []

    for lid, license_info in SAT_LICENSE_DEFS.items():
        for sat_num in license_info["satellites"]:
            name = f"FM{sat_num}"
            name = SPIRE_ID_OVERRIDES.get(name, name)
            defs.append(asset(name, SATELLITE, lid))

    _run_statements(defs)


def _create_ground_stations() -> None:
    stations = set()

    def lid(station: str) -> str:
        return f"{station}_gs_license"

    for countries in GS_LICENSE_DEFS.values():
        for allowed_stations in countries.values():
            for station in allowed_stations:
                stations.add(station)
    defs = [asset(station, GROUND_STATION, lid(station)) for station in stations]

    _run_statements(defs)


def _create_channels() -> None:
    defs = []

    for cid, channel_info in CHANNEL_DEFS.items():
        defs.append(channel({"id": cid, **channel_info}))

        for bid, band_info in BAND_DEFS.items():
            band = band_info["band"]
            for req in channel_info["all_of"]:
                band_req = req["band"]
                if band == band_req:
                    defs.append(channel_frequency(cid, bid))

    _run_statements(defs)


def load_license_data() -> None:
    _create_frequency_bands()
    _create_licenses()
    _create_satellites()
    _create_ground_stations()
    _create_channels()


def _shared_asset_channel_defs(
    asset_id: str, cid: str, channel_def: ChannelDefinition
) -> List[str]:
    defs = []
    lp_id = f"{asset_id}_{cid}_profile"
    ps_id = f"{asset_id}_{cid}_params"
    # Note: In a production migration link profiles and parameter sets should be de-duplicated.
    defs.append(
        link_profile(
            lp_id, channel_def["link_profile"], channel_def["contact_overhead_time"]
        )
    )
    defs.append(parameter_set(ps_id, channel_def.get("window_parameters", {})))
    defs.append(
        asset_channel_config(
            asset_id,
            cid,
            link_profile=lp_id,
            parameter_set=ps_id,
            enabled=channel_def["enabled"],
        )
    )
    return defs


def _ingest_ground_station_config(asset_id: str, config: AssetConfig) -> None:
    defs = []

    for cid, channel_def in config.items():
        defs.extend(_shared_asset_channel_defs(asset_id, cid, channel_def))

        if con := channel_def.get("ground_station_constraints"):
            con_id = f"{asset_id}_{cid}_constraints"
            defs.append(constraint_definition(con_id, GROUND_STATION, con))
            defs.append(operational_constraint(asset_id, cid, con_id))

    _run_statements(defs)


def _ingest_satellite_config(asset_id: str, config: AssetConfig) -> None:
    defs = []

    for cid, channel_def in config.items():
        defs.extend(_shared_asset_channel_defs(asset_id, cid, channel_def))

        if con := channel_def.get("satellite_constraints"):
            con_id = f"{asset_id}_{cid}_constraints"
            defs.append(constraint_definition(con_id, SATELLITE, con))
            defs.append(operational_constraint(asset_id, cid, con_id))

    _run_statements(defs)


def ingest_assets(env: Environment, assets: List[str]) -> None:
    for asset in locate_assets(env, assets):
        config = load_asset_config(env, asset)
        kind = infer_asset_type(asset)

        print("Ingesting config for", env, kind, asset)

        if kind == GROUND_STATION:
            _ingest_ground_station_config(asset, config)
        else:
            _ingest_satellite_config(asset, config)
