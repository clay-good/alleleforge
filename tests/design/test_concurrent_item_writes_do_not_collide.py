"""Two workers writing the same output path must not share a temp file.

`_atomic_write_text` named its temp file `<path>.<pid>.tmp`, which is unique per
*process*. It runs inside `_design_one`, which runs in a worker thread, so every thread
in a parallel cohort shared that name -- and two items with the same id resolve to the
same output path and therefore the same temp path. A variant repeated in a VCF is
ordinary, and `--max-workers` is on `aforge batch`.

Both threads then write one file and both rename it. Observed: the first `os.replace`
moves the shared temp away and the second raises `FileNotFoundError`, which the cohort
catches and records as "unexpected FileNotFoundError (likely a defect)" against an item
whose data was fine. Other interleavings leave the two payloads mixed in one file --
in the export the module docstring calls lossless.

The atomicity itself was never the problem: temp-file-plus-`os.replace` is right, and
the encoding pin above it is right. The name was the problem.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from alleleforge.design.cohort import _atomic_write_text

#: Big enough that a single write is not one syscall, so an interleaving has room to
#: happen rather than being hidden by the payload being tiny.
PAYLOAD = 200_000


def _write_concurrently(target: Path, texts: list[str]) -> list[BaseException]:
    """Write every text to ``target`` from its own thread, released together."""
    barrier = threading.Barrier(len(texts))
    errors: list[BaseException] = []

    def writer(text: str) -> None:
        barrier.wait()
        try:
            _atomic_write_text(target, text)
        except BaseException as exc:  # noqa: BLE001 - the failure is what we are measuring
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(t,)) for t in texts]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_writers_to_one_path_all_succeed(tmp_path: Path) -> None:
    target = tmp_path / "item.json"
    texts = [json.dumps({"who": who, "pad": who * PAYLOAD}) for who in ("a", "b", "c")]

    errors = _write_concurrently(target, texts)

    assert not errors, f"a concurrent writer failed: {errors!r}"


def test_the_surviving_file_is_one_whole_payload(tmp_path: Path) -> None:
    """Not a mixture: last-writer-wins is fine, half of each is not."""
    target = tmp_path / "item.json"
    texts = [json.dumps({"who": who, "pad": who * PAYLOAD}) for who in ("a", "b", "c")]

    _write_concurrently(target, texts)

    raw = target.read_text()
    assert raw in texts, f"the file is not any of the written payloads (length {len(raw)})"
    json.loads(raw)  # ...and it parses, which a mixture would not


def test_no_temp_files_are_left_behind(tmp_path: Path) -> None:
    target = tmp_path / "item.json"
    _write_concurrently(target, [json.dumps({"n": n, "pad": "x" * PAYLOAD}) for n in range(3)])

    leftovers = sorted(p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp"))
    assert not leftovers, f"temp files survived the write: {leftovers}"


def test_the_ordinary_single_write_still_works(tmp_path: Path) -> None:
    """Guard the guard: the uniquifier must not break the normal path.

    Including the non-ASCII case the encoding pin above it exists for.
    """
    target = tmp_path / "item.json"
    payload = json.dumps({"gene": "β-globin"})

    _atomic_write_text(target, payload)

    assert target.read_text(encoding="utf-8") == payload
    assert json.loads(target.read_text(encoding="utf-8"))["gene"] == "β-globin"
