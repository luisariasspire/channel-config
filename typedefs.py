from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from mypy_extensions import TypedDict

Environment = Union[Literal["staging"], Literal["production"]]


class DefsFile(TypedDict):
    groups: Mapping[str, List[str]]


# TODO Derive types from JSON Schema or vice versa
class GsConstraints(TypedDict):
    pass


class SatConstraints(TypedDict):
    pass


class ChannelDefinition(TypedDict, total=False):
    legal: bool
    enabled: bool
    directionality: str  # TODO Stricter type
    allowed_license_countries: List[str]
    ground_station_constraints: GsConstraints
    satellite_constraints: SatConstraints


AssetConfig = Dict[str, Optional[ChannelDefinition]]

GroundStationKind = Literal["groundstation"]
SatelliteKind = Literal["satellite"]
AssetKind = Union[GroundStationKind, SatelliteKind]


class TkGroundStation(TypedDict):
    license_country: str


class TkSatellite(TypedDict):
    license_country: str
