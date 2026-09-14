"""The slate page's QR encoder, checked by decoding what it draws.

The encoder is hand-written into `slate/index.html` so the page needs no
downloads. That makes it the riskiest thing on the page: a QR code that is
subtly wrong does not throw an error, it just fails to decode in the lab, on
the one take that mattered. So these tests run the page's own encoder in Node
and decode every symbol with OpenCV -- the decoder ingest would use -- across
every version and error-correction level, including the capacity boundaries
where an off-by-one hides.

Skipped, not failed, when Node or OpenCV is not installed, so the rest of the
suite still runs on a machine without them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).resolve().parent.parent / "slate" / "index.html"
LEVELS = ["L", "M", "Q", "H"]
MAX_VERSION = 10

node = shutil.which("node")
cv2 = pytest.importorskip("cv2", reason="OpenCV decodes the symbols")
np = pytest.importorskip("numpy")
needs_node = pytest.mark.skipif(node is None, reason="Node runs the page's encoder")


def encoder_source() -> str:
    found = re.search(r"/\* qr-encoder:begin.*?\*/(.*?)/\* qr-encoder:end",
                      PAGE.read_text(encoding="utf-8"), re.S)
    assert found, "the encoder markers are missing from slate/index.html"
    return found.group(1)


def run_encoder(tmp_path: Path, jobs: list[dict]) -> list[dict]:
    """Encode every job with the page's own code, in one Node process."""
    harness = tmp_path / "harness.js"
    harness.write_text(
        encoder_source()
        + "\nconst jobs = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
          "const out = jobs.map(({text, ecl}) => {\n"
          "  try {\n"
          "    const q = QR.encode(text, ecl);\n"
          "    return {version: q.version, size: q.size,\n"
          "            rows: q.modules.map(r => r.map(m => m ? '1' : '0').join(''))};\n"
          "  } catch (e) { return {error: String(e.message)}; }\n"
          "});\n"
          "process.stdout.write(JSON.stringify(out));\n",
        encoding="utf-8")
    done = subprocess.run([node, str(harness)], input=json.dumps(jobs),
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=120)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def decode(symbol: dict) -> str:
    """Decode the way ingest will have to: two detectors, several scales.

    OpenCV's standard detector misses roughly 1 in 70 *valid, perfectly
    rendered* symbols at any one image scale -- measured over every length at
    every level while writing this. The same symbol reads at another scale, or
    through the ArUco-based detector. A symbol neither detector reads at any
    scale is the thing to worry about, because Reed-Solomon parity means a
    broken encoder cannot produce a false decode.
    """
    modules = np.array([[c == "1" for c in row] for row in symbol["rows"]])
    base = np.where(modules, 0, 255).astype(np.uint8)
    base = np.pad(base, 4, constant_values=255)             # quiet zone
    for detector in (cv2.QRCodeDetector(), cv2.QRCodeDetectorAruco()):
        for scale in (6, 4, 10):
            image = np.kron(base, np.ones((scale, scale), np.uint8))
            try:
                text, _, _ = detector.detectAndDecode(image)
            except cv2.error:
                continue
            if text:
                return text
    return ""


def filler(n: int, seed: int) -> str:
    """Deterministic, varied text, so different masks get chosen."""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789_-.:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    state = seed * 2654435761 % 2**32 or 1
    chars = []
    for _ in range(n):
        state = (state * 1103515245 + 12345) % 2**31
        chars.append(alphabet[state % len(alphabet)])
    return "".join(chars)


# -- the encoder -------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("ecl", LEVELS)
def test_every_version_decodes_including_the_capacity_boundaries(tmp_path, ecl):
    # Sweep every length once without decoding, to learn where each version
    # starts and ends; then decode the first and last length of every version.
    sweep = run_encoder(tmp_path, [{"text": filler(n, n), "ecl": ecl}
                                   for n in range(1, 300)])
    first, last = {}, {}
    for n, result in enumerate(sweep, start=1):
        if "error" in result:
            continue
        first.setdefault(result["version"], n)
        last[result["version"]] = n

    assert sorted(last) == list(range(1, MAX_VERSION + 1)), \
        "every version should be reachable"

    lengths = sorted(set(first.values()) | set(last.values()))
    jobs = [{"text": filler(n, n), "ecl": ecl} for n in lengths]
    for job, symbol in zip(jobs, run_encoder(tmp_path, jobs)):
        assert decode(symbol) == job["text"], \
            f"{ecl} version {symbol['version']}, {len(job['text'])} bytes"


@needs_node
def test_text_too_long_for_version_10_is_refused_not_truncated(tmp_path):
    [result] = run_encoder(tmp_path, [{"text": "x" * 400, "ecl": "M"}])
    assert "too long" in result["error"]


@needs_node
@pytest.mark.parametrize("text", [
    "pk1:20260212_hooper1_vertical-swimming:take03",
    "pk1:20260212_hooper1_vertical-swimming:take03:sync:0000",
    "pk1:20260212_hooper1_vertical-swimming:take03:sync:0007",
    "pk1:" + "a" * 128 + ":take999:sync:9999",       # the longest id allowed
])
def test_real_slate_payloads_decode(tmp_path, text):
    [symbol] = run_encoder(tmp_path, [{"text": text, "ecl": "M"}])
    assert decode(symbol) == text


@needs_node
def test_a_sync_payload_stays_small_enough_to_read_from_a_distance(tmp_path):
    """A typical id must fit a low version: bigger modules, easier to read."""
    [symbol] = run_encoder(tmp_path, [{
        "text": "pk1:20260212_hooper1_vertical-swimming:take03:sync:0007",
        "ecl": "M"}])
    assert symbol["version"] <= 4


@needs_node
def test_utf8_is_encoded_as_bytes(tmp_path):
    [symbol] = run_encoder(tmp_path, [{"text": "18 °C · µm", "ecl": "M"}])
    assert decode(symbol) == "18 °C · µm"


# -- the page ----------------------------------------------------------------

def test_the_page_loads_nothing_from_the_network():
    """One file that works offline, and never tells anyone what you record."""
    html = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.I)
    assert "fetch(" not in html and "XMLHttpRequest" not in html


def test_the_page_documents_the_payload_format():
    """Ingest will be written against this; the page is the spec."""
    html = PAGE.read_text(encoding="utf-8")
    assert "pk1:<experiment-id>:take03" in html
    assert "pk1:<experiment-id>:take03:sync:0007" in html
    assert "BLACK when k is even" in html
