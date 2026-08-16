from pathlib import Path

from scripts.discover_3dvault import human_label, is_hashlike_label, label_for
from scripts.discover_3dvault_named_projects import resolve_slugs, slugs_from_probe


def test_hashed_image_filenames_are_not_collection_names():
    hashed = "a070778ef833cf2df144246cb7427a05_0f2e535b90d4ee3b4c34ca0d706b8190.jpg"
    assert is_hashlike_label(hashed)
    assert is_hashlike_label(f"https://drive.baako.com/2023/08/_cache/{hashed}")
    assert not is_hashlike_label("CLONE X")
    assert human_label(hashed, "Partner Avatar Collections") == "Partner Avatar Collections"
    assert label_for({
        "text": "",
        "href": "",
        "images": [{"alt": hashed, "title": hashed, "src": hashed}],
    }) == ""


def test_named_project_slugs_merge_probe_without_duplicates(tmp_path: Path):
    probe = tmp_path / "probe.json"
    probe.write_text(
        '{"openseaSlugs": ["clonex", "new-partner-avatars", "CLONEX"]}',
        encoding="utf-8",
    )
    assert slugs_from_probe(probe) == ["clonex", "new-partner-avatars"]

    class Args:
        slugs = "clonex,thewynlambo"
        slugs_from = probe

    assert resolve_slugs(Args()) == ["clonex", "thewynlambo", "new-partner-avatars"]
