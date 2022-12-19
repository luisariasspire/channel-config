from typing import Dict, Optional, Tuple, Union

import requests

from channel_tool.typedefs import AssetKind, Environment, TkGroundStation, TkSatellite
from channel_tool.util import tk_url

TK_ASSET_CACHE: Dict[
    Tuple[str, str, Optional[str]], Union[TkGroundStation, TkSatellite]
] = {}


# TODO enum type for assets
def load_tk_asset(
    env: Environment, kind: AssetKind, name: Optional[str] = None
) -> Union[TkGroundStation, TkSatellite]:
    if (env, kind, name) not in TK_ASSET_CACHE:
        # TODO Load all of the assets to populate cache rather than fetching them one by one
        if name:
            suffix = f"/{name}"
        else:
            suffix = ""
        r = requests.get(tk_url(env) + kind + suffix)
        r.raise_for_status()
        val = r.json()
        TK_ASSET_CACHE[(env, kind, name)] = val
        return val  # type: ignore
    else:
        return TK_ASSET_CACHE[(env, kind, name)]
