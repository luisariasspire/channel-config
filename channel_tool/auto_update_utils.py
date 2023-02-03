import sys
import warnings
import csv
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

    return int(ema * result_safety_factor)


def simple_moving_average(
    history: list[float], history_length_days: int, result_safety_factor: float
) -> float:
    return int(
        average(history[len(history) - history_length_days :]) * result_safety_factor
    )


def read_history(
    column: str, source_file: str, conversion_factor: float
) -> list[float]:
    goodput = []
    # From the documentation: If csvfile is a file object, it should be opened with newline=''
    # https://docs.python.org/3/library/csv.html

    with open(source_file, newline="", encoding="utf-8-sig") as f:
        contents = csv.DictReader(f)
        print(contents)
        for line_number, row in enumerate(contents):
            try:
                # Zero goodput means no data
                if row[column] != "0":
                    goodput.append(int(row[column]) * conversion_factor)
            except IndexError:
                warnings.warn(f"Empty line on {source_file} {line_number} skipped")
            except ValueError:
                warnings.warn(f"Non-int value on {source_file} {line_number} skipped")
            except KeyError:
                sys.exit(f"No column named {column} was found in {source_file}.")

    return goodput


def create_config_updates(args: Any) -> List[Mapping[str, Any]]:
    """
    Creates the new value for the parameter.
    Returns it in the format expected by the update function.
    """

    history = read_history(args.data_column, args.source_file, args.conversion_factor)

    assert (
        len(history) >= args.history_length
    ), "History length cannot be longer than data provided."

    if args.calculation_method == "sma":
        new_value = simple_moving_average(
            history, args.history_length, args.safety_factor
        )
    else:
        new_value = exponential_moving_average(
            history, args.history_length, args.safety_factor
        )

    key = (
        "downlink_rate_kbps"
        if args.parameter == "link_profile"
        else "contact_overhead_time"
    )

    return [{key: new_value}]


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
    elif asset not in min_elevation_10:
        warnings.warn(
            f"There is no predicate definition for asset {asset}. No filters will be applied."
        )

    return None
