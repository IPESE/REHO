"""Tests for path resolution and the tabular file reader."""

import os

import pandas as pd
import pytest

from reho import paths


class TestPackagePaths:
    @pytest.mark.parametrize(
        "name",
        [
            "path_to_data", "path_to_model", "path_to_plotting", "path_to_ampl_model",
            "path_to_units", "path_to_district_units", "path_to_units_interperiod",
            "path_to_elcom", "path_to_infrastructure",
            "path_to_qbuildings", "path_to_mobility", "path_to_sia",
            "path_to_sia_equivalence", "path_to_sia_norms", "path_to_skydome", "path_to_actor",
        ],
    )
    def test_shipped_paths_exist(self, name):
        assert os.path.exists(getattr(paths, name)), f"{name} does not exist in the installed package"


class TestWorkingDirectoryPaths:
    def test_paths_follow_the_working_directory(self, tmp_path, monkeypatch):
        # Resolving these at import time would freeze whatever directory the
        # interpreter started in, and send clustering files to the wrong place.
        monkeypatch.chdir(tmp_path)
        assert paths.path_to_clustering == os.path.join(str(tmp_path), "data", "clustering")
        assert paths.path_to_configurations == os.path.join(str(tmp_path), "results", "configurations")

    def test_unknown_attribute_raises(self):
        with pytest.raises(AttributeError):
            paths.path_to_nowhere


class TestPathHandler:
    def test_absolute_path(self, tmp_path):
        target = tmp_path / "file.csv"
        target.write_text("a,b\n1,2\n")
        assert paths.path_handler(str(target)) == str(target)

    def test_relative_path(self, tmp_path, monkeypatch):
        (tmp_path / "file.csv").write_text("a,b\n1,2\n")
        monkeypatch.chdir(tmp_path)
        assert paths.path_handler("file.csv").endswith("file.csv")

    def test_missing_file_message_mentions_the_working_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="working directory"):
            paths.path_handler("absent.csv")


class TestFileReader:
    @pytest.mark.parametrize("delimiter", [",", ";", "\t"])
    def test_delimiter_is_detected(self, tmp_path, delimiter):
        target = tmp_path / "data.csv"
        target.write_text(f"a{delimiter}b\n1{delimiter}2\n")
        df = paths.file_reader(str(target))
        assert list(df.columns) == ["a", "b"]
        assert df.iloc[0].tolist() == [1, 2]

    def test_index_col(self, tmp_path):
        target = tmp_path / "data.csv"
        target.write_text("a,b\nx,2\n")
        assert paths.file_reader(str(target), index_col=0).index.tolist() == ["x"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            paths.file_reader(str(tmp_path / "absent.csv"))

    def test_unreadable_file_raises_instead_of_returning_none(self, tmp_path):
        # Returning None here used to turn a bad input file into an opaque
        # AttributeError much further down the pipeline.
        target = tmp_path / "data.xlsx"
        target.write_bytes(b"this is not a spreadsheet")
        with pytest.raises(ValueError, match="Could not read"):
            paths.file_reader(str(target))

    def test_shipped_layers_file(self):
        df = paths.file_reader(os.path.join(paths.path_to_infrastructure, "layers.csv"))
        assert isinstance(df, pd.DataFrame)
        assert "Grid" in df.columns
