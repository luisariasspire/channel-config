import csv
import sys
import warnings
from typing import Any, Callable, List, Mapping

warnings.formatwarning = lambda msg, *args, **kwargs: f"Warning: {msg}\n"


def average(l: list[float]) -> float:
    return sum(l) / len(l)


def exponential_moving_average(
    history: list[float],
    history_length_days: int,
    result_safety_factor: float,
    smoothing: int = 2,
) -> float:
    # Below is the standard EMA formula implemented manually
    # to avoid importing modules unnecessarily
    factor = smoothing / (1 + history_length_days)
    ema = simple_moving_average(history, history_length_days, result_safety_factor)

    for i in range(1, len(history)):
        ema = history[i] * factor + ema * (1 - factor)

    return round(float(ema * result_safety_factor), 2)


def simple_moving_average(
    history: list[float], history_length_days: int, result_safety_factor: float
) -> float:
    return round(
        float(
            average(history[len(history) - history_length_days :])
            * result_safety_factor
        ),
        2,
    )


def read_history(
    column: str, source_file: str, conversion_factor: float
) -> Mapping[str, list[float]]:
    goodput = {}  # type: ignore
    # If csvfile is a file object, it should be opened with newline=''
    # https://docs.python.org/3/library/csv.html
    with open(source_file, newline="", encoding="utf-8-sig") as f:
        contents = csv.DictReader(f)
        sorted_contents = sorted(contents, key=lambda row: row["sync_id"])
        for row in sorted_contents:
            try:
                goodput.setdefault(row["channel_id"], []).append(
                    float(row[column]) * conversion_factor
                )
            except IndexError:
                warnings.warn(f"Empty line on {source_file} skipped")
            except ValueError:
                warnings.warn(
                    f"Non-float value {row[column]} on {source_file} sync_id:{row['sync_id']} skipped"
                )
            except KeyError as e:
                sys.exit(f"No column named {e} was found in {source_file}.")

    return goodput


def create_config_updates(
    args: Any, history: list[float]
) -> List[Mapping[str, Any]] | str:
    """
    Creates the new value for the parameter.
    Returns it in the format expected by the update function.
    """

    if args.calculation_method == "sma":
        new_value = simple_moving_average(history, len(history), args.safety_factor)
    else:
        new_value = exponential_moving_average(
            history, len(history), args.safety_factor
        )

    if args.parameter == "link_profile":
        return [{"downlink_rate_kbps": new_value}]
    else:
        return str(int(new_value)) + "s"


def asset_to_predicates(asset: str, compiler: Callable[[str], Any]) -> Any:
    """
    Takes a ground station ID and returns predicate functions that filters it's
    UHF link profiles out. As active ground stations change, These lists should
    be updated manually. Note that this function returns a list, more than one
    predicate may be compiled if necessary.
    """
    asset = asset.upper()
    min_elevation_25 = [
        "ANCGS",
        "BDLGS",
        "BDUGS",
        "CLTGS",
        "CMBGS",
        "DALGS",
        "DLHGS",
        "GLAGS",
        "GUMGS",
        "ITOGS",
        "IVCGS",
        "JNBGS",
        "JNUGS",
        "ORKGS",
        "PITGS",
        "PUQGS",
        "SEAGS",
        "SMAGS",
        "STXGS",
        "VNTGS",
        "XSPGS",
        "BDAGS",
        "ACCGS",
        "HLEGS",
        "HNDGS",
        "IBRGS",
        "PSYGS",
        "SINGS",
        "TUSGS",
        "WBUGS",
    ]
    min_elevation_10 = ["AWAGS", "TOSGS", "ICEGS", "PERGS"]

    if asset in min_elevation_25:
        return [compiler("min_elevation_deg >= 25")]
    elif asset in min_elevation_10:
        return [compiler("min_elevation_deg >= 10")]

    warnings.warn(
        f"There is no predicate definition for asset {asset}. No filters will be applied."
    )

    return None
