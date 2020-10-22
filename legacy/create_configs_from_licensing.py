from licensing import gs_licensed_freqs
from ruamel.yaml import YAML
from collections import defaultdict
import sys

yaml = YAML()
with open("contact_type_defs.yaml") as f:
    CHANNEL_DEFS = yaml.load(f)["contact_types"]


def allows_use(lic, band_def):
    """Test if a license allows use of a directional frequency band."""
    def is_allowed(band):
        if band["earth_to_space"] and not lic.uplink:
            return False
        if band["space_to_earth"] and not lic.downlink:
            return False
        center_freq = ((band["band"][0] + band["band"][1]) / 2) * 1000 * 1000  # Convert to Hz
        if not lic.contains(center_freq):
            return False
        return True

    if "any_of" in band_def:
        for b in band_def["any_of"]:
            if is_allowed(b):
                return True
        return False
    else:
        return is_allowed(band_def)


def can_use(cdef, licenses):
    """Test if a contact type can be used, given a set of licenses."""
    for band in cdef["all_of"]:
        if not any([allows_use(lic, band) for lic in licenses]):
            return False
    return True


def normalize(country):
    """Normalize licensing country identifiers to ISO-3166 country codes."""
    return country.split("_")[0]


def invert_dict(d):
    """Invert the keys and values of a dictionary whose values are lists."""
    di = {}
    for k, vs in d.items():
        for v in vs:
            x = di.get(v, [])
            x.append(k)
            di[v] = x
    return di


def find_legal_contact_types(cdefs, gs_license):
    """Find the legal contact types, by country, for a ground station with the given license."""
    license_sets = defaultdict(list)
    # We combine all of the licenses for a ground station per-country because the channel
    # representation can handle country exclusions without requiring us to create new names like
    # "US_II". The ground station is licensed to use all of these frequencies; it's the satellite
    # that needs to consider what ground stations it talks to.
    for country, licenses in gs_license.items():
        license_sets[normalize(country)].extend(licenses)
    contact_types_by_country = {
        c: [ctype for ctype, cdef in cdefs.items() if can_use(cdef, license_set)]
        for c, license_set in license_sets.items()
    }
    return invert_dict(contact_types_by_country)


def format_commands(gs_id, gs_chans):
    cmds = []
    for contact_type, countries in gs_chans.items():
        c_str = ",".join(countries)
        # TODO Add comments with license justification
        cmds.append(f"./channel_tool add {gs_id} {contact_type}"
                    f" --allowed_license_countries={c_str}"
                    " --legal true"  # Override legality: the license exists.
                    " --yes")
    return cmds


for gs, lics in gs_licensed_freqs.items():
    gs_chans = find_legal_contact_types(CHANNEL_DEFS, lics)
    for cmd in format_commands(gs, gs_chans):
        print(cmd)
