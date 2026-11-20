"""Fixtures for the file handling lesson (Track L, testing-file-handling-and-path-traversal).

``make_tree`` builds a small directory tree in a temporary folder - an uploads folder with a sibling folder whose
name starts the same way, a secret outside it, and two symbolic links - so the containment exercises run against
a real file system, not a simulation. ``PNG`` / ``JPG`` / ``PDF`` / ``HTML`` are tiny byte strings that start with
the real file signatures; none of them is a complete file. Everything is synthetic and stays on this machine.

Layout under ``root`` (every file contains its own relative path, so a test can tell which file it read)::

    root/secret.txt                     <- outside the base folder: must never be served
    root/uploads/terms.txt              <- the public folder (the "base")
    root/uploads/reports/2026-11.txt
    root/uploads/link-inside.txt        -> terms.txt          (a link that stays inside the base)
    root/uploads/link-outside.txt       -> ../secret.txt      (a link that leaves the base)
    root/uploads-old/old.txt            <- shares the prefix "uploads" with the base
"""

from __future__ import annotations

from pathlib import Path

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic image body"
JPG = b"\xff\xd8\xff\xe0" + b"synthetic image body"
PDF = b"%PDF-1.7\n" + b"synthetic document body"
HTML = b"<html><script>synthetic page</script></html>"


def make_tree(root: Path, symlinks: bool = True) -> dict[str, Path]:
    """Creates the tree under ``root`` and returns ``{"base": ..., "secret": ..., "old": ...}``.

    ``symlinks=False`` skips the two links (a Windows account without the symlink privilege cannot create them).
    """
    files = {
        "secret.txt": "secret.txt\n",
        "uploads/terms.txt": "uploads/terms.txt\n",
        "uploads/reports/2026-11.txt": "uploads/reports/2026-11.txt\n",
        "uploads-old/old.txt": "uploads-old/old.txt\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    if symlinks:
        (root / "uploads" / "link-inside.txt").symlink_to("terms.txt")
        (root / "uploads" / "link-outside.txt").symlink_to("../secret.txt")
    return {"base": root / "uploads", "secret": root / "secret.txt", "old": root / "uploads-old"}
