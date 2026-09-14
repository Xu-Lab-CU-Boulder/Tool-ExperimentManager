"""The slate's QR payloads, parsed.

    slate   pk1:<experiment-id>:take03
    sync    pk1:<experiment-id>:take03:sync:0007

The format is defined by `slate/index.html`, which is the spec. Anything that
does not parse is not ours -- a QR code on a product label, a poster in the
background -- and is ignored rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from projectkit.dataset import validate_id

PREFIX = "pk1"

_CODE = re.compile(
    r"^pk1:(?P<id>[^:]+):take(?P<take>\d{2,3})(?::sync:(?P<sync>\d{4}))?$")


@dataclass(frozen=True)
class SlateCode:
    """One decoded payload."""
    dataset_id: str
    take: int
    sync: int | None = None          # the flip counter, for a sync code

    @property
    def is_sync(self) -> bool:
        return self.sync is not None

    @property
    def take_folder(self) -> str:
        return take_folder(self.take)


def take_folder(take: int) -> str:
    """`take03`, matching what the slate shows. Three digits past 99."""
    return f"take{take:02d}"


def parse(text: str) -> SlateCode | None:
    """A payload from the slate, or None if this QR code is not one.

    The id is checked with projectkit's own rule, so a code can only ever name
    something that could be a dataset.
    """
    found = _CODE.match(text.strip())
    if not found:
        return None
    dataset_id = found.group("id")
    try:
        validate_id(dataset_id)
    except ValueError:
        return None
    take = int(found.group("take"))
    if not 1 <= take <= 999:
        return None
    sync = found.group("sync")
    return SlateCode(dataset_id, take, int(sync) if sync is not None else None)
