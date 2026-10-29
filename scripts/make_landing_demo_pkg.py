"""
Write the small `weathervault` package that the README's demo recording documents

The landing demo (`docs/assets/landing-demo.termshow.yml`) runs `great-docs init`,
`build`, and `preview` on this package in a scratch directory, so the recording
shows Great Docs' real output. Regenerate the recording with `make landing-demo`.

Usage:

    python scripts/make_landing_demo_pkg.py DEST
"""

from __future__ import annotations

import argparse
import shutil
import textwrap
from pathlib import Path

_INIT = '''\
"""Collect, convert, and summarize weather station observations"""

__version__ = "2.4.1"

from .convert import dew_point, heat_index, to_celsius, to_fahrenheit, wind_chill
from .io import load_csv, save_csv
from .models import Forecast, Observation, Station
from .stats import daily_summary, rolling_mean

__all__ = [
    "Station",
    "Observation",
    "Forecast",
    "to_celsius",
    "to_fahrenheit",
    "heat_index",
    "wind_chill",
    "dew_point",
    "load_csv",
    "save_csv",
    "daily_summary",
    "rolling_mean",
]
'''

_MODELS = '''\
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Station:
    """
    A weather station

    Parameters
    ----------
    code
        The station's identifier, such as `"KSEA"`.
    name
        A readable name for the station.
    latitude
        Latitude in decimal degrees.
    longitude
        Longitude in decimal degrees.
    """

    code: str
    name: str
    latitude: float
    longitude: float

    def distance_to(self, other: Station) -> float:
        """
        Distance to another station, in kilometres

        Parameters
        ----------
        other
            The station to measure to.

        Returns
        -------
        float
            The great-circle distance.
        """
        from math import asin, cos, radians, sin, sqrt

        dlat = radians(other.latitude - self.latitude)
        dlon = radians(other.longitude - self.longitude)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(self.latitude)) * cos(radians(other.latitude)) * sin(dlon / 2) ** 2
        )
        return 2 * 6371 * asin(sqrt(a))


@dataclass
class Observation:
    """
    One reading from a station

    Parameters
    ----------
    station
        The station that made the reading.
    time
        When the reading was made, as an ISO 8601 string.
    temperature
        Air temperature in degrees Celsius.
    humidity
        Relative humidity, from 0 to 100.
    wind_speed
        Wind speed in km/h.
    """

    station: Station
    time: str
    temperature: float
    humidity: float = 50.0
    wind_speed: float = 0.0


@dataclass
class Forecast:
    """
    A forecast for one station

    Parameters
    ----------
    station
        The station the forecast is for.
    hours
        Forecast temperatures, one per hour.
    """

    station: Station
    hours: list[float] = field(default_factory=list)

    def high(self) -> float:
        """
        The highest forecast temperature

        Returns
        -------
        float
            The maximum of `hours`.
        """
        return max(self.hours)

    def low(self) -> float:
        """
        The lowest forecast temperature

        Returns
        -------
        float
            The minimum of `hours`.
        """
        return min(self.hours)
'''

_CONVERT = '''\
from __future__ import annotations

from math import log


def to_celsius(fahrenheit: float) -> float:
    """
    Convert a temperature from Fahrenheit to Celsius

    Parameters
    ----------
    fahrenheit
        The temperature in degrees Fahrenheit.

    Returns
    -------
    float
        The temperature in degrees Celsius.

    Examples
    --------
    ```python
    to_celsius(212)
    ```
    """
    return (fahrenheit - 32) * 5 / 9


def to_fahrenheit(celsius: float) -> float:
    """
    Convert a temperature from Celsius to Fahrenheit

    Parameters
    ----------
    celsius
        The temperature in degrees Celsius.

    Returns
    -------
    float
        The temperature in degrees Fahrenheit.
    """
    return celsius * 9 / 5 + 32


def heat_index(temperature: float, humidity: float) -> float:
    """
    How hot it feels, given the temperature and humidity

    Parameters
    ----------
    temperature
        Air temperature in degrees Celsius.
    humidity
        Relative humidity, from 0 to 100.

    Returns
    -------
    float
        The apparent temperature in degrees Celsius.
    """
    t = to_fahrenheit(temperature)
    hi = -42.379 + 2.04901523 * t + 10.14333127 * humidity - 0.22475541 * t * humidity
    return to_celsius(hi)


def wind_chill(temperature: float, wind_speed: float) -> float:
    """
    How cold it feels, given the temperature and wind speed

    Parameters
    ----------
    temperature
        Air temperature in degrees Celsius.
    wind_speed
        Wind speed in km/h.

    Returns
    -------
    float
        The apparent temperature in degrees Celsius.
    """
    v = wind_speed**0.16
    return 13.12 + 0.6215 * temperature - 11.37 * v + 0.3965 * temperature * v


def dew_point(temperature: float, humidity: float) -> float:
    """
    The temperature at which dew forms

    Parameters
    ----------
    temperature
        Air temperature in degrees Celsius.
    humidity
        Relative humidity, from 0 to 100.

    Returns
    -------
    float
        The dew point in degrees Celsius.
    """
    gamma = log(humidity / 100) + 17.62 * temperature / (243.12 + temperature)
    return 243.12 * gamma / (17.62 - gamma)
'''

_IO = '''\
from __future__ import annotations

import csv
from pathlib import Path

from .models import Observation, Station


def load_csv(path: str | Path, station: Station) -> list[Observation]:
    """
    Read observations from a CSV file

    Parameters
    ----------
    path
        A CSV file with `time`, `temperature`, `humidity`, and `wind_speed` columns.
    station
        The station the observations came from.

    Returns
    -------
    list[Observation]
        One observation per row.
    """
    with open(path, newline="") as f:
        return [
            Observation(
                station,
                row["time"],
                float(row["temperature"]),
                float(row["humidity"]),
                float(row["wind_speed"]),
            )
            for row in csv.DictReader(f)
        ]


def save_csv(observations: list[Observation], path: str | Path) -> None:
    """
    Write observations to a CSV file

    Parameters
    ----------
    observations
        The observations to write.
    path
        Where to write them.
    """
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "temperature", "humidity", "wind_speed"])
        for o in observations:
            writer.writerow([o.time, o.temperature, o.humidity, o.wind_speed])
'''

_STATS = '''\
from __future__ import annotations

from .models import Observation


def daily_summary(observations: list[Observation]) -> dict[str, float]:
    """
    Summarize a day of observations

    Parameters
    ----------
    observations
        Observations from a single day.

    Returns
    -------
    dict[str, float]
        The `high`, `low`, and `mean` temperature.
    """
    temps = [o.temperature for o in observations]
    return {"high": max(temps), "low": min(temps), "mean": sum(temps) / len(temps)}


def rolling_mean(values: list[float], window: int = 3) -> list[float]:
    """
    Smooth a series with a moving average

    Parameters
    ----------
    values
        The series to smooth.
    window
        How many values each average covers.

    Returns
    -------
    list[float]
        The averages, one per complete window.
    """
    return [sum(values[i : i + window]) / window for i in range(len(values) - window + 1)]
'''

_PYPROJECT = """\
[project]
name = "weathervault"
version = "2.4.1"
description = "Collect, convert, and summarize weather station observations"
readme = "README.md"
requires-python = ">=3.10"

[project.urls]
Documentation = "https://weathervault.example.org"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""

_README = """\
# weathervault

Collect, convert, and summarize weather station observations.

```python
import weathervault as wv

wv.to_celsius(72)
```
"""

_GUIDE = {
    "01-getting-started.qmd": ("Getting Started", "Install weathervault and read your first file."),
    "02-stations.qmd": ("Stations", "Find stations and measure the distance between them."),
    "03-conversions.qmd": ("Conversions", "Convert temperatures and compute how hot it feels."),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("dest", type=Path)
    args = parser.parse_args()

    dest: Path = args.dest
    if dest.exists():
        shutil.rmtree(dest)
    pkg = dest / "weathervault"
    pkg.mkdir(parents=True)
    for name, text in {
        "__init__.py": _INIT,
        "models.py": _MODELS,
        "convert.py": _CONVERT,
        "io.py": _IO,
        "stats.py": _STATS,
    }.items():
        (pkg / name).write_text(text, encoding="utf-8")
    (dest / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (dest / "README.md").write_text(_README, encoding="utf-8")

    guide = dest / "docs" / "user_guide"
    guide.mkdir(parents=True)
    for name, (title, body) in _GUIDE.items():
        text = textwrap.dedent(f"""\
            ---
            title: "{title}"
            ---

            {body}
            """)
        (guide / name).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
