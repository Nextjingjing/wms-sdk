import pathlib
import re

import pytest

from dev.gen_schema_doc import OUTPUTS, render

DOCS = pathlib.Path("docs")
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def pages(lang: str) -> set[str]:
    return {p.name for p in (DOCS / lang).glob("*.md")}


@pytest.mark.parametrize("lang", sorted(OUTPUTS))
def test_schema_doc_is_up_to_date(lang):
    current = OUTPUTS[lang].read_text(encoding="utf-8")
    assert current == render(lang), f"{OUTPUTS[lang]} is stale: run python -m dev.gen_schema_doc"


def test_both_languages_have_the_same_pages():
    assert pages("en") == pages("th")


@pytest.mark.parametrize("lang, other", [("en", "th"), ("th", "en")])
def test_every_page_links_to_its_counterpart(lang, other):
    missing = [
        name
        for name in pages(lang)
        if f"](../{other}/{name})" not in (DOCS / lang / name).read_text(encoding="utf-8")
    ]
    assert missing == []


def test_relative_links_point_to_existing_files():
    files = [*DOCS.rglob("*.md"), pathlib.Path("README.md"), pathlib.Path("README.th.md")]
    broken = [
        (str(f), target)
        for f in files
        for target in LINK.findall(f.read_text(encoding="utf-8"))
        if not target.startswith(("http://", "https://")) and not (f.parent / target).exists()
    ]
    assert broken == []
