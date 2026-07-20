from app.spots.parser import (band_for, classify_mode, parse_spot_line,
                              split_hint)


def test_classic_line():
    s = parse_spot_line("DX de W3LPL:     14023.0  3Y0K         UP 2 loud         1834Z")
    assert s is not None
    assert s.spotter == "W3LPL"
    assert s.dx_call == "3Y0K"
    assert s.freq == 14023.0
    assert s.band == "20m"
    assert s.mode == "CW"
    assert s.split_tx_khz == 14025.0


def test_line_with_grid_suffix():
    s = parse_spot_line("DX de VE7CC-#:   21074.5  5Z4VJ        FT8 -12 dB        0912Z <FN20>")
    assert s is not None
    assert s.mode == "FT8"
    assert s.spotter == "VE7CC"


def test_non_spot_lines():
    assert parse_spot_line("WWV de W0MU <18>:   SFI=168, A=6, K=2") is None
    assert parse_spot_line("login: ") is None
    assert parse_spot_line("") is None


def test_band_classification():
    assert band_for(1823.5) == "160m"
    assert band_for(50313) == "6m"
    assert band_for(9000) == ""


def test_mode_by_frequency():
    assert classify_mode(14074.8, "") == "FT8"      # FT8 window
    assert classify_mode(14080.5, "") == "FT4"      # FT4 window
    assert classify_mode(14012.0, "") == "CW"       # CW segment
    assert classify_mode(14250.0, "") == "SSB"
    assert classify_mode(7074.0, "") == "FT8"


def test_comment_beats_frequency():
    assert classify_mode(14074.0, "CW up 1") == "CW"
    assert classify_mode(14005.0, "FT8 dxped freq") == "FT8"


def test_split_hints():
    assert split_hint(14023.0, "UP 2") == 14025.0
    assert split_hint(14023.0, "up") == 14025.0            # bare up -> +2
    assert split_hint(7005.0, "DN 1") == 7004.0
    assert split_hint(14023.0, "QSX 14027.5") == 14027.5
    assert split_hint(14023.0, "tnx 599") is None


def test_wpm_comment_is_cw():
    assert classify_mode(14090.0, "22 WPM loud") == "CW"
