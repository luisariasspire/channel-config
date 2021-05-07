#! /usr/bin/env python3

import os

from ruamel.yaml import YAML

yaml = YAML()

lookup_table = {
    "sat": {
        "CONTACT_BIDIR": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 10.0,
                }
            ]
        },
        "CONTACT_BIDIR_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 10.0,
                }
            ]
        },
        "CONTACT_BIDIR_UHF": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 10.0,
                    "uplink_rate_kbps": 10.0,
                }
            ]
        },
        "CONTACT_RXO": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_RXO_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_TRACKING_BIDIR": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 10.0,
                }
            ]
        },
        "CONTACT_TRACKING_BIDIR_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 10.0,
                }
            ]
        },
        "CONTACT_TRACKING_RXO": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_TRACKING_RXO_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_RXO_DVBS2X_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_RXO_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_TRACKING_RXO_DVBS2X_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
        "CONTACT_TRACKING_RXO_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 1000.0,
                    "uplink_rate_kbps": 0.0,
                }
            ]
        },
    },
    "gs": {
        "CONTACT_BIDIR": {
            "link_profile": [
                {
                    "min_elevation_deg": 10,
                    "downlink_rate_kbps": 5.6,
                    "uplink_rate_kbps": 5.6,
                },
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 300,
                    "uplink_rate_kbps": 5.6,
                    "min_duration": "20sec",
                },
            ]
        },
        "CONTACT_BIDIR_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 10,
                    "downlink_rate_kbps": 5.6,
                    "uplink_rate_kbps": 5.6,
                },
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 350,
                    "uplink_rate_kbps": 5.6,
                    "min_duration": "20sec",
                },
            ]
        },
        "CONTACT_BIDIR_UHF": {
            "link_profile": [
                {
                    "min_elevation_deg": 0,
                    "downlink_rate_kbps": 5.6,
                    "uplink_rate_kbps": 5.6,
                }
            ]
        },
        "CONTACT_RXO": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 240.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_RXO_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 280.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_TRACKING_BIDIR": {
            "link_profile": [
                {
                    "min_elevation_deg": 10,
                    "downlink_rate_kbps": 5.6,
                    "uplink_rate_kbps": 5.6,
                },
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 300,
                    "uplink_rate_kbps": 5.6,
                    "min_duration": "20sec",
                },
            ]
        },
        "CONTACT_TRACKING_BIDIR_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 10,
                    "downlink_rate_kbps": 5.6,
                    "uplink_rate_kbps": 5.6,
                },
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 350,
                    "uplink_rate_kbps": 5.6,
                    "min_duration": "20sec",
                },
            ]
        },
        "CONTACT_TRACKING_RXO": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 240.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_TRACKING_RXO_DVBS2X": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 280.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_RXO_DVBS2X_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 280.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_RXO_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 240.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_TRACKING_RXO_DVBS2X_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 240.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
        "CONTACT_TRACKING_RXO_SBAND_FREQ_2200_MHZ": {
            "link_profile": [
                {
                    "min_elevation_deg": 25,
                    "downlink_rate_kbps": 240.0,
                    "uplink_rate_kbps": 0.0,
                    "min_duration": "2min",
                }
            ]
        },
    },
}


def add_elevation_bands(env: str):
    for asset_type in ["gs", "sat"]:
        directory = f"../{env}/{asset_type}"
        for filename in os.listdir(directory):
            with open(os.path.join(directory, filename)) as f:
                channel_configs = yaml.load(f)
            for name, properties in channel_configs.items():
                link_profile = lookup_table[asset_type][name]
                properties["link_profile"] = link_profile["link_profile"]
            with open(os.path.join(directory, filename), "w") as f:
                yaml.dump(channel_configs, f)


def main():
    add_elevation_bands("production")


if __name__ == "__main__":
    main()
