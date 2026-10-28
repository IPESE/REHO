"""Tests for the preprocessing of the model inputs: typical periods, SIA profiles, web queries."""

import os

import numpy as np
import pandas as pd
import pytest

from reho.model.preprocessing import weather
from reho.model.preprocessing.buildings_profiles import annual_to_typical
from reho.model.preprocessing.electricity_prices import requests_retry_session
from reho.model.preprocessing.sia_parser import (
    daily_profiles_with_monthly_deviation,
    read_sia2024_rooms_sia380_1,
    read_sia_2024_profiles,
)
from reho.paths import path_to_sia_equivalence, path_to_sia_norms

HOURS = 24


def _three_kinds_of_day(days=365, seed=0):
    """Weather data cycling through three very different days, so that consecutive days never
    belong to the same cluster. Over a full year, the coldest hour is on day 41 and the hottest
    on day 201."""
    rng = np.random.default_rng(seed)
    hour = np.arange(HOURS)
    shapes = [
        (np.full(HOURS, -2.0), np.zeros(HOURS)),
        (8 + 4 * np.sin(np.pi * hour / HOURS), 300 * np.sin(np.pi * hour / HOURS)),
        (22 + 6 * np.sin(np.pi * hour / HOURS), 800 * np.sin(np.pi * hour / HOURS)),
    ]
    text = np.concatenate([shapes[d % 3][0] for d in range(days)]) + rng.normal(0, 0.1, days * HOURS)
    irr = np.concatenate([shapes[d % 3][1] for d in range(days)]).clip(min=0)
    if days > 200:
        text[40 * HOURS + 5] = -15.0
        text[200 * HOURS + 14] = 35.0
    time = pd.date_range("2005-01-01", periods=days * HOURS, freq="h")
    return pd.DataFrame({"Text": text, "Irr": irr, "Weekday": (time.weekday < 5).astype(int)},
                        index=pd.Index(time.strftime("%Y-%m-%d %H:%M:%S"), name="time(UTC)"))


def _read_index_csv(directory):
    """Typical period of each hour of the year, as written to ``index.csv``."""
    with open(os.path.join(directory, "index.csv")) as handle:
        rows = [line.split() for line in handle if line[0].isdigit()]
    return {int(hour): int(period) for hour, period, _ in rows}


class TestTypicalPeriods:
    @pytest.fixture(scope="class")
    def clustering_directory(self, tmp_path_factory):
        directory = tmp_path_factory.mktemp("clustering")
        weather_file = directory / "weather.csv"
        _three_kinds_of_day().to_csv(weather_file)
        cluster = {"custom_weather": str(weather_file), "Location": "Synthetic", "Attributes": ["T", "I", "W"],
                   "Periods": 3, "PeriodDuration": HOURS}
        weather.generate_weather_data(cluster, {}, str(directory))
        return directory

    def test_typical_periods_are_the_medoid_days(self, clustering_directory):
        annual = pd.read_csv(clustering_directory / "annual_data.csv")
        typical = pd.read_csv(clustering_directory / "typical_data.csv")
        timestamp = pd.read_csv(clustering_directory / "timestamp.csv")
        period_of_hour = _read_index_csv(clustering_directory)

        typical_periods = timestamp.iloc[:-2]
        assert typical_periods["Frequency"].sum() == 365
        for position, period in enumerate(typical_periods.itertuples()):
            first_hour = (period.SourcePeriod - 1) * HOURS
            day = annual.iloc[first_hour: first_hour + HOURS]
            profile = typical.iloc[position * HOURS: (position + 1) * HOURS]
            np.testing.assert_allclose(profile[["Text", "Irr"]].to_numpy(), day[["Text", "Irr"]].to_numpy())
            # The day the profile comes from belongs to the cluster it represents.
            assert period_of_hour[first_hour + 1] == period.Day

    def test_extreme_periods_are_dated_on_their_day(self, clustering_directory):
        timestamp = pd.read_csv(clustering_directory / "timestamp.csv", parse_dates=["Date"])
        coldest, hottest = timestamp["Date"].iloc[-2], timestamp["Date"].iloc[-1]
        assert coldest.dayofyear == 41
        assert hottest.dayofyear == 201

    def test_generated_files_are_marked_as_current(self, clustering_directory):
        assert weather.typical_periods_are_current(str(clustering_directory))

    def test_outdated_or_foreign_files_are_not_current(self, tmp_path):
        assert not weather.typical_periods_are_current(str(tmp_path))
        (tmp_path / weather.TYPICAL_PERIODS_VERSION_FILE).write_text("1")
        assert not weather.typical_periods_are_current(str(tmp_path))
        (tmp_path / weather.TYPICAL_PERIODS_VERSION_FILE).write_text("not a version")
        assert not weather.typical_periods_are_current(str(tmp_path))


def test_annual_to_typical_with_a_leftover_period(tmp_path):
    """Weekly periods leave 24 hours over in a year: they form a shorter period of their own."""
    weather_file = tmp_path / "weather.csv"
    _three_kinds_of_day().to_csv(weather_file)
    cluster = {"custom_weather": str(weather_file), "Location": "Synthetic", "Attributes": ["T", "I", "W"],
               "Periods": 3, "PeriodDuration": 168}
    weather.generate_weather_data(cluster, {}, str(tmp_path))
    timestamp = pd.read_csv(tmp_path / "timestamp.csv")

    annual_file = tmp_path / "profile.csv"
    pd.DataFrame({"time(UTC)": pd.date_range("2005-01-01", periods=8760, freq="h"),
                  "Elec": np.arange(8760)}).to_csv(annual_file, index=False)
    typical = annual_to_typical(cluster, annual_file, timestamp)

    hours = typical.groupby(level="Period").size()
    assert list(hours) == [168] * 3 + [24, 1, 1]
    for period, source_period in enumerate(timestamp["SourcePeriod"].iloc[:-2], start=1):
        assert typical.loc[(period, 1), "Elec"] == (source_period - 1) * 168
    assert typical.loc[(5, 1), "Elec"] == 0 and typical.loc[(6, 1), "Elec"] == 8759


class TestClusterFileID:
    def test_attributes_are_ordered(self):
        cluster = {"Location": "Geneva", "Attributes": ["W", "T", "I"], "Periods": 10, "PeriodDuration": 24}
        assert weather.get_cluster_file_ID(cluster) == "Geneva_10_24_T_I_W"

    def test_unknown_attribute_raises(self):
        cluster = {"Location": "Geneva", "Attributes": ["T", "I", "E"], "Periods": 10, "PeriodDuration": 24}
        with pytest.raises(ValueError, match="'E'"):
            weather.get_cluster_file_ID(cluster)

    def test_new_options_are_part_of_the_id(self):
        cluster = {"Location": "Geneva", "Attributes": ["T", "I", "W"], "Periods": 10, "PeriodDuration": 24,
                   "Year": [2021, 2022, 2023], "Scenario": "rcp45_2050"}
        assert weather.get_cluster_file_ID(cluster) == "Geneva_10_24_T_I_W_2021-2023_rcp45_2050"


class TestSIAProfiles:
    @pytest.fixture(scope="class")
    def sia_2024(self):
        return pd.read_excel(path_to_sia_norms, sheet_name=["profiles", "calculs", "data"], engine="openpyxl",
                             index_col=[0], skiprows=[0, 2, 3, 4], header=[0])

    def test_electrical_heat_gains_come_from_appliances_and_lighting(self, sia_2024):
        rooms = read_sia2024_rooms_sia380_1("I", pd.read_csv(path_to_sia_equivalence, sep=";", index_col=[0], header=[0]))
        additional_lighting = read_sia_2024_profiles("standard", sia_2024)[0]
        # Housing has no additional (showroom) lighting, so all its electricity turns into gains.
        assert not additional_lighting.multiply(rooms.values, axis=0).dropna().to_numpy().any()

        profiles = daily_profiles_with_monthly_deviation("standard", rooms, pd.Timestamp("2005-01-12"), sia_2024)

        np.testing.assert_allclose(profiles["elecgain_W/m2"], 0.7 * profiles["electricity_W/m2"])
        assert profiles["elecgain_W/m2"].sum() > 0


class TestWebQueries:
    def test_retries_apply_to_http_and_https(self):
        session = requests_retry_session(retries=5)
        for url in ("http://example.org", "https://example.org"):
            assert session.get_adapter(url).max_retries.total == 5
