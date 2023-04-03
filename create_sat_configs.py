#! /usr/bin/env python3

# This script generates commands for the channel configuration tool `channel_tool` to add licenses
# for satellites based on data in the `sat_license_defs.yaml` file. The commands will not modify
# existing licenses, but will add any new ones. Note that this will populate the legal channel
# definitions, but won't take into consideration factors like whether S-band is currently enabled
# for a satellite.

# To generate and run all of the channel addition commands, use:
# poetry run python create_sat_configs.py | xargs -L 1 poetry run

import sys

from ruamel.yaml import YAML

yaml = YAML()
with open("contact_type_defs.yaml") as f:
    CHANNEL_DEFS = yaml.load(f)["contact_types"]

with open("sat_license_defs.yaml") as f:
    y = yaml.load(f)
    SAT_LICENSE_DEFS = y["licenses"]
    ALL_ISO_COUNTRIES = y["definitions"]["all_iso_countries"]
    SPIRE_COUNTRIES = y["definitions"]["spire_gs_countries"]
    SPIRE_ID_OVERRIDES = y["definitions"]["spire_id_overrides"]


# TODO Combine with the definition in create_gs_configs_from_licensing.py
def allows_use(licensed_freqs, band_def):
    """Test if a license allows use of a channel, based on its required frequency bands."""

    def has_matching_freq(band_low, band_high, band_dir):
        for freq in licensed_freqs:
            lic_low = freq[0]
            lic_high = freq[1]
            lic_dir = freq[2]
            if lic_low <= band_low and band_high <= lic_high and band_dir == lic_dir:
                return True
        return False

    def is_allowed(band):
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


# TODO Combine with the definition in create_gs_configs_from_licensing.py
def can_use(cdef, lic):
    """Test if a contact type can be used, given a set of licenses."""
    for band in cdef["all_of"]:
        if not allows_use(lic["frequencies"], band):
            return False
    return True


def find_channels(lic, cdefs):
    return [cname for (cname, cdef) in cdefs.items() if can_use(cdef, lic)]


def spire_id(sat):
    name = f"FM{sat}"
    return SPIRE_ID_OVERRIDES.get(name, name)


def emit_channel_commands(sats, channels, countries):
    country_list = ",".join(countries)
    channel_list = ",".join(channels)
    fms = ",".join([spire_id(sat) for sat in sats])
    # TODO Should the script update the "is legal" bit on existing channels?
    print(
        f"python -m channel_tool add staging {fms}"
        f" {channel_list}"
        f" --allowed_license_countries={country_list}"
        " --legal=True --yes"
    )


def main():
    for lic_name, lic in SAT_LICENSE_DEFS.items():
        print(
            f"Processing license {lic_name}",
            file=sys.stderr,
        )

        allowed_countries = [
            c for c in SPIRE_COUNTRIES if c not in lic["blacklisted_countries"]
        ]
        allowed_channels = find_channels(lic, CHANNEL_DEFS)
        sats = lic["satellites"]
        if not allowed_countries or not allowed_channels or not sats:
            print(
                f"Error: Missing country, channel, or satellite definitions for license {lic_name}",
                file=sys.stderr,
            )
            sys.exit(1)
        emit_channel_commands(sats, allowed_channels, allowed_countries)


if __name__ == "__main__":
    main()
