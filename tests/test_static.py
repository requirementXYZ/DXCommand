"""Static integrity of the frontend: catches broken references and the
hidden-vs-display overlay regression without needing a browser."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "css" / "style.css").read_text(encoding="utf-8")
JS_FILES = sorted((STATIC / "js").glob("*.js"))


def test_referenced_assets_exist():
    for src in re.findall(r'<script src="([^"]+)"', INDEX):
        assert (STATIC / src).exists(), f"missing script {src}"
    for href in re.findall(r'<link rel="stylesheet" href="([^"]+)"', INDEX):
        assert (STATIC / href).exists(), f"missing stylesheet {href}"


def test_hidden_attribute_beats_display_rules():
    """Overlays use display:flex by id; the [hidden] guard must exist or they
    render permanently (the CW-trainer-stuck-open bug)."""
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important", CSS)


def test_overlays_start_hidden():
    for overlay in ("cw-overlay", "settings-overlay", "help-overlay"):
        m = re.search(rf'<div id="{overlay}"([^>]*)>', INDEX)
        assert m, f"{overlay} missing"
        assert "hidden" in m.group(1), f"{overlay} must start hidden"


def test_js_element_ids_exist_in_html():
    """Every literal id used via $("...") or getElementById must exist in
    index.html (or be created dynamically in that same JS file)."""
    html_ids = set(re.findall(r'id="([^"]+)"', INDEX))
    for js in JS_FILES:
        text = js.read_text(encoding="utf-8")
        created = set(re.findall(r'\.id\s*=\s*"([^"]+)"', text))
        used = set(re.findall(r'\$\("([^"]+)"\)', text))
        used |= set(re.findall(r'getElementById\("([^"]+)"\)', text))
        missing = used - html_ids - created
        assert not missing, f"{js.name} references unknown ids: {sorted(missing)}"


def test_info_tooltips_present():
    tips = re.findall(r'class="info" data-tip="([^"]+)"', INDEX)
    assert len(tips) >= 9, "expected an info icon on every major panel"
    assert all(len(t) > 40 for t in tips), "tooltips should be instructive, not stubs"


def test_help_overlay_has_quick_start():
    assert "QUICK START" in INDEX
    assert "help-overlay" in INDEX
