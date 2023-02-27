from ruamel import yaml
import sys
import re
from typing import Dict, Any, Optional, Union

pls_mtu_map = {
    # short frame PLS values
    7: 372,
    11: 642,
    15: 777,
    19: 867,
    23: 1182,
    27: 1317,
    31: 1452,
    35: 1542,
    39: 1632,
    43: 1767,
    75: 1182,
    79: 1317,
    83: 1452,
    87: 1632,
    91: 1767,
    # long frame PLS values
    5: 1989,
    9: 2664,
    13: 3204,
    17: 4014,
    21: 4824,
    25: 5368,
    29: 6039,
    33: 6444,
    37: 6718,
    41: 7172,
    45: None,
    49: 4824,
    53: 5368,
    57: 6039,
    61: 6718,
    65: 7172,
    # error
    "Not available": "Not available",
}

pls_snr_req = {
    # short frame
    7: -2.35,
    11: -1.24,
    15: -0.3,
    19: 1,
    23: 2.23,
    27: 3.1,
    31: 4.03,
    35: 4.68,
    39: 5.18,
    43: 6.2,
    75: 9.27,
    79: 10.51,
    83: 11.33,
    87: 11.91,
    91: 13.19,
    # long frame
    5: -2.35,
    9: -1.24,
    13: -0.3,
    17: 1,
    21: 2.23,
    25: 3.1,
    29: 4.03,
    33: 4.68,
    37: 5.18,
    41: 6.2,
    # 45: None,
    49: 5.5,
    53: 6.62,
    57: 7.91,
    61: 9.35,
    65: 10.69,
    # error
    "Not available": -99999,
}

pls_speed = {
    # short
    7: 0.274,
    11: 0.471,
    15: 0.57,
    19: 0.636,
    23: 0.866,
    27: 0.965,
    31: 1.064,
    35: 1.13,
    39: 1.195,
    43: 1.294,
    75: 1.732,
    79: 1.93,
    83: 2.127,
    87: 2.391,
    91: 2.588,
    # long
    5: 4.097,
    9: 5.486,
    13: 6.597,
    17: 8.263,
    21: 9.93,
    25: 11.049,
    29: 12.43,
    33: 13.263,
    37: 13.827,
    41: 14.761,
    # 45: 14.947, -- missing data
    49: 14.895,
    53: 16.574,
    57: 18.645,
    61: 20.741,
    65: 22.142,
    # 69: 22.42,
}

pls_short = {7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 75, 79, 83, 87, 91}
pls_long = {
    5,
    9,
    13,
    17,
    21,
    25,
    29,
    33,
    37,
    41,
    49,
    53,
    57,
    61,
    65,
}  # note 45 is omitted - no data


# YAML template support
def load_expand(loader: yaml.loader.BaseLoader, node: yaml.nodes.Node) -> Any:
    value = loader.construct_scalar(node)
    var = re.search(r"\$\{(.*)\}", value)
    if not var:
        raise ValueError(f"match not found in {value}")
    return loader.vars.get(var.group(1))


def load_notnull(
    loader: yaml.loader.BaseLoader, node: yaml.nodes.Node
) -> Dict[str, Any]:
    mapping = loader.construct_mapping(node)
    return {k: v for k, v in mapping.items() if k is not None and bool(v)}


def load_radionet(
    loader: yaml.loader.BaseLoader, node: yaml.nodes.Node
) -> Optional[Any]:
    if loader.args.radionet:
        return loader.construct_scalar(node)
    return None


def pls_lookup(args: Any) -> None:
    """
    module main entry point
    """
    found: Dict[str, Optional[Union[float, str]]] = {"pls": None, "mtu": None}
    if args.radionet:
        print("Radionet enabled")
        found["radionet"] = True

    if args.sband:
        found["band"] = "SBAND"
        found["mode"] = "TX_SBAND_DVB_IP" if args.radionet else "TX_SBAND_DVB"
        filt_sp = {v: k for k, v in pls_speed.items() if k in pls_short}
    elif args.xband:
        found["band"] = "XBAND"
        found["mode"] = "TX_XBAND_DVB_IP" if args.radionet else "TX_XBAND_DVB"
        filt_sp = {v: k for k, v in pls_speed.items() if k in pls_long}
    else:
        filt_sp = {v: k for k, v in pls_speed.items()}

    if args.pls is not None:
        if args.sband and args.pls not in pls_short:
            raise ValueError(f"pls {args.pls} not valid for sband")
        if args.xband and args.pls not in pls_long:
            raise ValueError(f"pls {args.pls} not valid for xband")
        found["pls"] = args.pls
        found["mtu"] = pls_mtu_map[args.pls]
        print(
            f"pls: {args.pls}  mtu: {pls_mtu_map[args.pls]} req SnR: {pls_snr_req[args.pls] + args.iovdb} speed: {pls_speed[args.pls]}"
        )
    else:
        reqd = args.db - args.iovdb

        found_pls: Union[int, str] = "Not available"
        found_db = float("-inf")
        speed = 0.0
        for sp in sorted(filt_sp.keys()):
            pls = filt_sp[sp]
            db_req = pls_snr_req[pls]
            if db_req > reqd:
                break
            found_pls = pls
            found_db = db_req
            speed = sp
        print(
            f"pls: {found_pls}  mtu: {pls_mtu_map[found_pls]}  req SnR: {found_db + args.iovdb} speed: {speed}Mbps"
        )
        found["pls"] = found_pls
        found["mtu"] = pls_mtu_map[found_pls]

    if not (args.xband or args.sband):
        print("Specify sband or xband to generate template")
    else:
        print(f"---using template {args.template}---")
        loader = yaml.loader.SafeLoader
        loader.vars = found
        loader.args = args
        loader.add_implicit_resolver("!var", re.compile("\$\{"), None)
        loader.add_constructor("!var", load_expand)
        loader.add_constructor("!notnull", load_notnull)
        loader.add_constructor("!radionet", load_radionet)
        with open(args.template) as t:
            tmpl = yaml.load(t, Loader=loader)
        print(yaml.dump(tmpl, default_flow_style=False))
