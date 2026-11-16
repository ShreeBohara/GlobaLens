"""The `srclc` check: every source-language code in a set of GKG files is in the language table."""

import os
import zipfile
from pathlib import Path

import pytest
from gdelt.srclc_check import SrclcReport, check_paths, main

GOLDEN = Path(__file__).parent / "golden"
WEEK_VARIABLE = "GLOBALENS_FIXTURE_WEEK"


def gkg_line(seq: int, code: str | None) -> bytes:
    columns = [b"x"] * 27
    columns[0] = f"20260301120000-T{seq}".encode()
    columns[1] = b"20260301120000"
    columns[25] = b"" if code is None else f"srclc:{code};eng:GT 1.0".encode()
    return b"\t".join(columns)


def write_csv(path: Path, codes: list[str | None]) -> Path:
    path.write_bytes(b"\n".join(gkg_line(i, code) for i, code in enumerate(codes)) + b"\n")
    return path


def test_known_codes_pass(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "20260301120000.translation.gkg.csv", ["fra", "axe", "fra", "zho"])
    report = check_paths([path])
    assert isinstance(report, SrclcReport)
    assert report.ok
    assert report.codes == {"fra": 2, "axe": 1, "zho": 1}
    assert report.unknown == {}
    assert (report.files, report.rows, report.days) == (1, 4, ("20260301",))


def test_an_unknown_code_fails(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "20260301120000.translation.gkg.csv", ["fra", "zzz", "zzz"])
    report = check_paths([path])
    assert not report.ok
    assert report.unknown == {"zzz": 2}


def test_zips_and_directories_are_read(tmp_path: Path) -> None:
    for day in ("20260301", "20260302"):
        csv = write_csv(tmp_path / f"{day}120000.translation.gkg.csv", ["deu", "ita"])
        with zipfile.ZipFile(tmp_path / f"{day}120000.translation.gkg.csv.zip", "w") as archive:
            archive.write(csv, csv.name)
        csv.unlink()
    write_csv(tmp_path / "20260301120000.gkg.csv", [None, None])  # the English stream has no code
    (tmp_path / "notes.txt").write_text("not a GKG file")
    report = check_paths([tmp_path])
    assert report.ok
    assert (report.files, report.rows, report.days) == (3, 6, ("20260301", "20260302"))
    assert report.codes == {"deu": 2, "ita": 2}


def test_malformed_lines_are_counted_not_read(tmp_path: Path) -> None:
    path = tmp_path / "20260301120000.translation.gkg.csv"
    path.write_bytes(
        gkg_line(0, "fra") + b"\nsrclc:zzz in a broken line\n\n" + gkg_line(1, "spa") + b"\n"
    )
    report = check_paths([path])
    assert report.ok and report.codes == {"fra": 1, "spa": 1} and report.malformed_lines == 1


def test_the_week_requirement(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "20260301120000.translation.gkg.csv", ["fra"])
    assert check_paths([path], require_days=1).ok
    short = check_paths([path], require_days=7)
    assert not short.ok and short.unknown == {} and short.days == ("20260301",)


def test_no_files_is_a_failure(tmp_path: Path) -> None:
    assert not check_paths([tmp_path]).ok


def test_command_line_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = write_csv(tmp_path / "20260301120000.translation.gkg.csv", ["fra"])
    assert main([str(good)]) == 0
    assert '"ok": true' in capsys.readouterr().out
    bad = write_csv(tmp_path / "20260302120000.translation.gkg.csv", ["zzz"])
    assert main([str(bad)]) == 1
    assert '"zzz": 1' in capsys.readouterr().out
    assert main(["--require-days", "7", str(good)]) == 1


def test_the_golden_fixtures_hold_exactly_one_unknown_code() -> None:
    report = check_paths(sorted(GOLDEN.glob("*.tsv")))
    assert report.unknown == {"zzz": 1}


def test_a_week_of_real_data_has_no_unknown_code() -> None:
    """The plan's `srclc` contract: a week of values, 0 unknown codes.

    The real fixture week stays on the owner's machine, outside the repository (design note
    Q19), so this runs only where GLOBALENS_FIXTURE_WEEK names the folder that holds it.
    """
    folder = os.environ.get(WEEK_VARIABLE)
    if not folder:
        pytest.skip(f"{WEEK_VARIABLE} is not set: the week-long srclc check did not run")
    report = check_paths([Path(folder)], require_days=7)
    assert report.unknown == {}, f"codes missing from gdelt.lang: {report.unknown}"
    assert report.ok, f"{len(report.days)} days found, 7 needed"
