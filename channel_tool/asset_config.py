import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

from ruamel.yaml.comments import CommentedMap

from channel_tool.typedefs import (
    AssetConfig,
    Environment,
    GroundStationKind,
    SatelliteKind,
)
from channel_tool.util import (
    GROUND_STATION,
    GS_DIR,
    SAT_DIR,
    SATELLITE,
    dump_yaml_file,
    dump_yaml_string,
    load_yaml_file,
)

CONFIG_CACHE: Dict[Tuple[str, str], AssetConfig] = {}


def locate_assets(env: Environment, assets: Union[str, List[str]]) -> List[str]:
    def name(p: str) -> str:
        return os.path.splitext(os.path.basename(p))[0]

    def group(g: str) -> Optional[List[str]]:
        assetGroups: Dict[str, List[str]] = load_yaml_file("asset_groups.yaml")
        return assetGroups.get(g)

    if isinstance(assets, list):
        return assets
    elif assets == "all_gs":
        return sorted([name(p) for p in os.listdir(os.path.join(env, GS_DIR))])
    elif assets == "all_sat":
        return sorted([name(p) for p in os.listdir(os.path.join(env, SAT_DIR))])
    elif assets == "all":
        vs = locate_assets(env, "all_gs")
        vs.extend(locate_assets(env, "all_sat"))
        return vs
    elif asset_group := group(assets):
        return asset_group
    else:
        return assets.split(",")


def infer_asset_type(asset: str) -> Union[GroundStationKind, SatelliteKind]:
    if asset.endswith("gs") or asset.endswith("kl"):
        return GROUND_STATION
    else:
        return SATELLITE


def infer_config_file(env: Environment, asset: str) -> str:
    asset_type = infer_asset_type(asset)
    if asset_type == GROUND_STATION:
        # Assumed to be a ground station.
        return os.path.join(env, GS_DIR, asset + ".yaml")
    elif asset_type == SATELLITE:
        # Assumed to be a satellite.
        return os.path.join(env, SAT_DIR, asset + ".yaml")
    else:
        raise ValueError(f"Unexpected asset type {asset_type}")


def load_asset_config(env: Environment, asset: str) -> AssetConfig:
    def do_load() -> AssetConfig:
        config_file = infer_config_file(env, asset)
        if not os.path.exists(config_file):
            return {}
        config: Optional[AssetConfig] = load_yaml_file(config_file)
        if config:
            return config
        else:
            return {}

    if not (env, asset) in CONFIG_CACHE:
        config = do_load()
        CONFIG_CACHE[(env, asset)] = config
        return config
    else:
        return CONFIG_CACHE[(env, asset)]


def write_asset_config(env: Environment, asset: str, asset_config: AssetConfig) -> None:
    config_file = infer_config_file(env, asset)
    if asset_config:
        asset_config = normalize_config(asset_config)
        dump_yaml_file(asset_config, config_file)
    elif os.path.exists(config_file):
        os.remove(config_file)


def asset_config_to_string(asset_config: AssetConfig) -> str:
    asset_config = normalize_config(asset_config)
    str_result: str = dump_yaml_string(asset_config)
    return str_result


def normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a configuration file by removing anchors and sorting keys."""
    new_config: Dict[str, Any] = CommentedMap()
    for k in sorted(cfg):
        new_config[k] = deepcopy(cfg[k])
    return new_config
