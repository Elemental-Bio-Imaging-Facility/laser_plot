import numpy as np
import os

from util.exceptions import PewPewConfigError, PewPewDataError, PewPewFileError
from util.formatter import formatIsotope
from util.laser import LaserData


def importCsv(path, isotope="Unknown", config=None, calibration=None, read_config=True):
    with open(path, "r") as fp:
        line = fp.readline().strip()
        if line == "# Pew Pew Export":  # CSV generated by pewpew
            isotope = fp.readline().strip().lstrip("# ")
            # Read the config from the file
            if read_config:
                config = LaserData.DEFAULT_CONFIG
                line = fp.readline().strip().lstrip("# ")
                if ";" not in line or "=" not in line:
                    raise PewPewFileError(f"Malformed config line '{line}'.")

                for token in line.split(";"):
                    k, v = token.split("=")
                    if k not in config.keys():
                        raise PewPewConfigError(f"Invalid config key '{k}'.")
                    try:
                        config[k] = float(v)
                    except ValueError as e:
                        raise PewPewConfigError(f"Invalid value '{v}'.") from e

        try:
            data = np.genfromtxt(fp, delimiter=",", dtype=np.float64, comments="#")
        except ValueError as e:
            raise PewPewFileError("Could not parse file.") from e

    if data.ndim != 2:
        raise PewPewDataError(f"Invalid data dimensions '{data.ndim}'.")

    isotope = formatIsotope(isotope)

    structured = np.empty(data.shape, dtype=[(isotope, np.float64)])
    structured[isotope] = data
    return LaserData(
        data=structured,
        config=config,
        calibration=calibration,
        name=os.path.splitext(os.path.basename(path))[0],
        source=path,
    )


def importNpz(path, config_override=None, calibration_override=None):
    """Imports the numpy archive given. Both the config and calibration are
    read from the archive but can be overriden.

    path -> path to numpy archive
    config_override -> if not None will be applied to all imports
    calibration_override -> if not None will be applied to all imports

    returns list of LaserData/KrissKrossData"""
    lds = []
    npz = np.load(path)

    num_files = sum(1 for d in npz.files if "_data" in d)
    for i in range(0, num_files):
        name = (
            npz["_name"][i]
            if "_name" in npz.files
            else os.path.splitext(os.path.basename(path))[0]
        )
        type = npz["_type"][i] if "_type" in npz.files else LaserData
        if config_override is None:
            config = npz["_config"][i] if "_config" in npz.files else None
        else:
            config = config_override
        if calibration_override is None:
            calibration = (
                npz["_calibration"][i] if "_calibration" in npz.files else None
            )
        else:
            calibration = calibration_override
        lds.append(
            type(
                data=npz[f"_data{i}"],
                config=config,
                calibration=calibration,
                name=name,
                source=path,
            )
        )
    return lds


def importAgilentBatch(path, config, calibration=None):
    """Scans the given path for .d directories containg a  similarly named
       .csv file. These are imported as lines and sorted by their name.

       path -> path to the .b directory
       config -> config to be applied
       calibration -> calibration to be applied

       returns LaserData"""
    data_files = []
    with os.scandir(path) as it:
        for entry in it:
            if entry.name.lower().endswith(".d") and entry.is_dir():
                csv = entry.name[: entry.name.rfind(".")] + ".csv"
                csv = os.path.join(entry.path, csv)
                if not os.path.exists(csv):
                    raise PewPewFileError(f"Missing csv '{csv}'.")
                data_files.append(csv)
    # Sort by name
    data_files.sort()

    with open(data_files[0], "r") as fp:
        line = fp.readline()
        skip_header = 0
        while line and not line.startswith("Time [Sec]"):
            line = fp.readline()
            skip_header += 1

        skip_footer = 0
        if "Print" in fp.read().splitlines()[-1]:
            skip_footer = 1

    cols = np.arange(1, line.count(",") + 1)

    try:
        lines = [
            np.genfromtxt(
                f,
                delimiter=",",
                names=True,
                usecols=cols,
                skip_header=skip_header,
                skip_footer=skip_footer,
                dtype=np.float64,
            )
            for f in data_files
        ]
    except ValueError as e:
        raise PewPewFileError("Could not parse batch.") from e

    try:
        data = np.vstack(lines)
    except ValueError as e:
        raise PewPewDataError("Mismatched data.") from e

    # Format isotope names
    data.dtype.names = [formatIsotope(name) for name in data.dtype.names]

    return LaserData(
        data,
        config=config,
        calibration=calibration,
        name=os.path.splitext(os.path.basename(path))[0],
        source=path,
    )


# def importThermoiCapLaser(path, config, calibration=None):
#     """Imports data exported using \"Laser Data Reduction\".
#     CSVs in the given directory are imported as
#     lines in the image and are sorted by name.

#     path -> path to directory containing CSVs
#     config -> config to apply
#     calibration -> calibration to apply

#     returns LaserData"""
#     data_files = []
#     with os.scandir(path) as it:
#         for entry in it:
#             if entry.name.lower().endswith(".csv") and entry.is_file():
#                 data_files.append(entry.path)
#     # Sort by name
#     data_files.sort()

#     with open(data_files[0], "r") as fp:
#         line = fp.readline()
#         skip_header = 0
#         while line and not line.startswith("Time"):
#             line = fp.readline()
#             skip_header += 1

#         delimiter = line[-1]

#     cols = np.arange(1, line.count(delimiter))

#     lines = [
#         np.genfromtxt(
#             f,
#             delimiter=delimiter,
#             names=True,
#             usecols=cols,
#             skip_header=skip_header,
#             dtype=np.float64,
#         )
#         for f in data_files
#     ]
#     # We need to skip the first row as it contains junk
#     data = np.vstack(lines)[1:]

#     return LaserData(data, config=config, calibration=calibration, source=path)


def importThermoiCapCSV(path, config, calibration=None):
    """Imports data exported using the CSV export function.
    Exports must include the \"Counts\" column.

    path -> path to CSV
    config -> config to apply
    calibration -> calibration to apply

    returns LaserData"""
    data = {}
    with open(path, "r") as fp:
        # Find delimiter
        line = fp.readline().strip()
        delimiter = line[-1]
        # Skip row
        line = fp.readline()
        # First real row
        line = fp.readline()
        while line:
            try:
                _, _, isotope, data_type, line_data = line.split(delimiter, 4)
                if data_type == "Counter":
                    data.setdefault(formatIsotope(isotope), []).append(
                        np.genfromtxt(
                            [line_data],
                            delimiter=delimiter,
                            dtype=np.float64,
                            filling_values=0.0,
                        )
                    )
            except ValueError as e:
                raise PewPewFileError("Could not parse file.") from e
            line = fp.readline()

    # Read the keys to ensure order is same
    keys = list(data.keys())
    # Stack lines to form 2d
    for k in keys:
        # Last line is junk
        data[k] = np.vstack(data[k])[:, :-1].transpose()
        if data[k].ndim != 2:
            raise PewPewDataError(f"Invalid data dimensions '{data.ndim}'.")

    # Build a named array out of data
    dtype = [(k, np.float64) for k in keys]
    shape = data[keys[0]].shape
    structured = np.empty(shape, dtype)
    for k in keys:
        if data[k].shape != shape:
            raise PewPewDataError("Mismatched data.")
        structured[k] = data[k]

    return LaserData(
        structured,
        config=config,
        calibration=calibration,
        name=os.path.splitext(os.path.basename(path))[0],
        source=path,
    )
