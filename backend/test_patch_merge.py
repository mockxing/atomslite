"""Standalone unit tests for the incremental patch merge (Continue Building).

Run:  python test_patch_merge.py
No third-party test framework required.
"""
import sys
import os

# Make app package importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
# Pydantic v2 forbids extra env vars; drop any stray ones that would break
# Settings() construction in the local test environment.
for _k in ("MODEL_POOL", "HUGGING_FACE_HUB_TOKEN", "HF_TOKEN"):
    os.environ.pop(_k, None)

from app.services.ai_service import apply_incremental_merge, _extract_block

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


B = "<<<REPLACE_BEGIN>>>"
AEND = "<<<REPLACE_ANCHOR_END>>>"
E = "<<<REPLACE_END>>>"


def test_extract_block():
    print("\n== _extract_block ==")
    t = f"{B}\n<body>\n{AEND}\n<BODY>\n{E}"
    check("anchor extracted", _extract_block(t, B, AEND) == "<body>")
    check("newcode extracted", _extract_block(t, AEND, E) == "<BODY>")
    check("missing begin", _extract_block("abc", B, AEND) == "")
    check("missing end", _extract_block(f"{B} x", B, AEND) == "")
    check("reversed", _extract_block(f"a{AEND}b{B} c", AEND, E) == "")


def test_merge_success():
    print("\n== merge: success ==")
    old = "<html><head><style>body{color:black}</style></head><body><h1>Hi</h1></body></html>"
    patch = (
        f"{B}\n<style>body{{color:black}}</style>\n{AEND}\n"
        "<style>body{color:black}body.dark{color:white}</style>\n"
        f"{E}"
    )
    out = apply_incremental_merge(old, patch)
    check("merged ok", out is not None)
    check("contains new", out is not None and "body.dark{color:white}" in out)
    check("preserves rest", out is not None and "<h1>Hi</h1>" in out and "<html>" in out)


def test_merge_anchor_missing():
    print("\n== merge: anchor missing ==")
    old = "<html><body><h1>Hi</h1></body></html>"
    patch = f"{B}\n<div id='nope'>\n{AEND}\n<b>new</b>\n{E}"
    check("anchor missing -> None", apply_incremental_merge(old, patch) is None)


def test_merge_anchor_duplicate():
    print("\n== merge: anchor duplicated ==")
    old = "<html><div>x</div><div>x</div></html>"
    patch = f"{B}\n<div>x</div>\n{AEND}\n<div>y</div>\n{E}"
    check("anchor duplicate -> None", apply_incremental_merge(old, patch) is None)


def test_merge_no_markers():
    print("\n== merge: no markers ==")
    old = "<html><body></body></html>"
    # A full-file rewrite (no REPLACE markers) must NOT be treated as a patch.
    out = apply_incremental_merge(old, "<html><body>full</body></html>")
    check("no markers -> None (falls back to full)", out is None)


def test_merge_empty_newcode():
    print("\n== merge: empty new code block ==")
    old = "<html><body><h1>Hi</h1></body></html>"
    patch = f"{B}\n<h1>Hi</h1>\n{AEND}\n{E}"
    check("empty replacement -> None (safe)", apply_incremental_merge(old, patch) is None)


def test_merge_broken_result():
    print("\n== merge: result loses closing body ==")
    old = "<html><body><h1>Hi</h1></body></html>"
    # Anchor is the whole <body>...</body>; new code drops </body>, so the
    # tag-balance validation must reject it.
    patch = f"{B}\n<body><h1>Hi</h1></body>\n{AEND}\n<body><h1>Broken</h1>\n{E}"
    check("broken result -> None", apply_incremental_merge(old, patch) is None)


def main():
    print("Running incremental patch merge tests...")
    test_extract_block()
    test_merge_success()
    test_merge_anchor_missing()
    test_merge_anchor_duplicate()
    test_merge_no_markers()
    test_merge_empty_newcode()
    test_merge_broken_result()
    print(f"\nResult: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
