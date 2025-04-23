from typing import Any, Dict

# Prefixes, one per "major class" of contact
U_U_BIDIR = "U_U_BIDIR"
S_U_BIDIR = "S_U_BIDIR"
S_TXO = "S_TXO"
X_TXO = "X_TXO"
X_S_BIDIR = "X_S_BIDIR"


KNOWN_PREFIX_MAP = {
    # (space_ground_uhf,
    #  ground_space_uhf,
    #  space_ground_sband,
    #  ground_space_sband,
    #  space_ground_xband)
    U_U_BIDIR: (True, True, False, False, False),
    S_U_BIDIR: (True, True, True, False, False),
    S_TXO: (False, False, True, False, False),
    X_TXO: (False, False, False, False, True),
    X_S_BIDIR: (False, False, False, True, True),
}


class ChannelNamingError(Exception):
    pass


def class_annos_to_name(class_annos: Dict[str, Any]) -> str:
    # establish prefix, which is based on the space-ground and ground-space radio bands
    band_booleans_tuple = (
        class_annos["space_ground_uhf"],
        class_annos["ground_space_uhf"],
        class_annos["space_ground_sband"],
        class_annos["ground_space_sband"],
        class_annos["space_ground_xband"],
    )
    prefix = None
    for known_prefix, prefix_booleans_tuple in KNOWN_PREFIX_MAP.items():
        if band_booleans_tuple == prefix_booleans_tuple:
            prefix = known_prefix
            break
    if not prefix:
        raise ChannelNamingError(
            f"No known major class prefix for classification annotations {class_annos}"
        )
    prov = generate_prov_section(class_annos)
    bw = generate_bw_section(class_annos)
    enc = generate_enc_section(class_annos)
    freq = generate_freq_section(class_annos)
    adcs = generate_adcs_section(class_annos)
    jira = generate_jira_section(class_annos)
    return f"{prefix}{prov}{bw}{enc}{freq}{adcs}{jira}"


def generate_prov_section(class_annos: Dict[str, Any]) -> str:
    provider = class_annos["provider"]
    return f"_{provider}"


def generate_bw_section(class_annos: Dict[str, Any]) -> str:
    if class_annos["space_ground_sband"]:
        bw = str(class_annos["space_ground_sband_bandwidth_mhz"])
        return f"_BW{bw}"
    elif class_annos["space_ground_xband"]:
        bw = str(class_annos["space_ground_xband_bandwidth_mhz"])
        return f"_BW{bw}"
    return ""


def generate_enc_section(class_annos: Dict[str, Any]) -> str:
    if class_annos["space_ground_sband"]:
        encoding = class_annos["space_ground_sband_encoding"]
        if encoding != "DVBS2X":
            return f"_LEG"
        pls = str(class_annos["space_ground_sband_dvbs2x_pls"])
        return f"_P{pls}"
    elif class_annos["space_ground_xband"]:
        pls = str(class_annos["space_ground_xband_dvbs2x_pls"])
        return f"_P{pls}"
    return ""


def generate_adcs_section(class_annos: Dict[str, Any]) -> str:
    adcs_pointing = class_annos["adcs_pointing"]
    return "" if adcs_pointing == "NADIR" else f"_{adcs_pointing}"


def generate_freq_section(class_annos: Dict[str, Any]) -> str:
    if class_annos["space_ground_sband"]:
        freq = str(class_annos["space_ground_sband_mid_freq_mhz"]).replace(".", "_")
        return f"_F{freq}"
    return ""


def generate_jira_section(class_annos: Dict[str, Any]) -> str:
    jira_ticket = class_annos.get("jira_ticket", None)
    if jira_ticket:
        jira_ticket = jira_ticket.replace("-", "_")
        return f"_JIRA_{jira_ticket}"
    return ""
