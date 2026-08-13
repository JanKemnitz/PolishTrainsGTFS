# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field
from io import Writer
from pathlib import Path
from typing import Literal, get_args
from xml.sax import parse as sax_parse
from xml.sax.handler import ContentHandler
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl as SAXAttributes

FeatureType = Literal["node", "way", "relation"]
VALID_FEATURE_TYPES: set[FeatureType] = set(get_args(FeatureType))

DEFAULT_PATH = Path("data/geo.osm")


@dataclass
class IDCounter:
    max: int = 0
    negative_count: int = 0

    def visit(self, id: int) -> None:
        self.max = max(self.max, id)
        self.negative_count += id < 0


@dataclass
class IDReplacer:
    counter: int = 0
    mapping: dict[int, int] = field(default_factory=dict[int, int])

    def get(self, id: int) -> int:
        if id > 0:
            return id

        if (replacement := self.mapping.get(id)) is None:
            self.counter += 1
            replacement = self.counter
            self.mapping[id] = replacement
        return replacement


class Checker(ContentHandler):
    nodes: IDCounter
    ways: IDCounter
    relations: IDCounter

    def __init__(self) -> None:
        self.nodes = IDCounter()
        self.ways = IDCounter()
        self.relations = IDCounter()

    def _get_counter(self, name: FeatureType) -> IDCounter:
        return getattr(self, f"{name}s")

    def startElement(self, name: str, attrs: SAXAttributes) -> None:
        if name in VALID_FEATURE_TYPES:
            id = int(attrs["id"])
            self._get_counter(name).visit(id)


class Fixer(XMLGenerator):
    nodes: IDReplacer
    ways: IDReplacer
    relations: IDReplacer

    def __init__(
        self,
        out: Writer[bytes],
        max_node_id: int = 0,
        max_way_id: int = 0,
        max_relation_id: int = 0,
    ) -> None:
        super().__init__(out, encoding="utf-8", short_empty_elements=True)
        self.nodes = IDReplacer(max_node_id)
        self.ways = IDReplacer(max_way_id)
        self.relations = IDReplacer(max_relation_id)

    def _get_replacer(self, name: FeatureType) -> IDReplacer:
        return getattr(self, f"{name}s")

    def startElement(self, name: str, attrs: SAXAttributes) -> None:
        if name in VALID_FEATURE_TYPES:
            original_id = int(attrs["id"])
            replacement_id = self._get_replacer(name).get(original_id)
            _set_attr(attrs, "id", str(replacement_id))
            if "version" not in attrs:
                _set_attr(attrs, "version", "1")

        elif name == "nd":
            original_id = int(attrs["ref"])
            replacement_id = self.nodes.get(original_id)
            _set_attr(attrs, "ref", str(replacement_id))

        elif name == "member" and (type := attrs["type"]) in VALID_FEATURE_TYPES:
            original_id = int(attrs["ref"])
            replacement_id = self._get_replacer(type).get(original_id)
            _set_attr(attrs, "ref", str(replacement_id))

        return super().startElement(name, attrs)


def _set_attr(attrs: SAXAttributes, k: str, v: str) -> None:
    attrs._attrs[k] = v  # type: ignore


def check(file: Path = DEFAULT_PATH) -> bool:
    checker = Checker()
    sax_parse(file, checker)

    ok = True

    if checker.nodes.negative_count:
        print(checker.nodes.negative_count, "nodes with unstable ids")
        ok = False

    if checker.ways.negative_count:
        print(checker.ways.negative_count, "ways with unstable ids")
        ok = False

    if checker.relations.negative_count:
        print(checker.relations.negative_count, "relations with unstable ids")
        ok = False

    return ok


def fix(file: Path = DEFAULT_PATH) -> None:
    checker = Checker()
    sax_parse(file, checker)

    tmp_file = file.with_name(f".{file.name}.tmp")
    try:
        with tmp_file.open("wb") as out:
            fixer = Fixer(out, checker.nodes.max, checker.ways.max, checker.relations.max)
            sax_parse(file, fixer)
    except BaseException:
        tmp_file.unlink(missing_ok=True)
        raise

    tmp_file.rename(file)


if __name__ == "__main__":
    from argparse import ArgumentParser
    from sys import exit

    arg_parser = ArgumentParser()
    arg_parser.add_argument("-c", "--check", action="store_true")
    arg_parser.add_argument("file", default=DEFAULT_PATH, type=Path, nargs="?")
    args = arg_parser.parse_args()

    if args.check:
        ok = check(args.file)
        exit(0 if ok else 1)
    else:
        fix(args.file)
        exit(0)
