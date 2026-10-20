"""The importer's last step: look again at what failed only because something wasn't installed *at the time*.

When several files are imported in a row each is linked against what is installed plus that one file, so a mention
of something that arrives with a later file stays plain text, and a subclass is refused if its class comes later.
``finalize_link_check`` (run once, after the last file) goes back over both.
"""

import pytest

import content_io

PREFIX = "Zqx"


def feat(name, description="Plain.", **extra):
    return {"name": f"{PREFIX} {name}", "description": description, "type": "General", **extra}


def import_in_a_row(*bundles, link_mentions=True):
    """What the Collections page does for several files: defer the check, merge, finalize once."""
    total = content_io.ImportReport()
    for bundle in bundles:
        total.merge(content_io.import_bundle(bundle, link_mentions=link_mentions, defer_link_check=True))
    content_io.finalize_link_check(total)
    return total


@pytest.fixture(autouse=True)
def clean_up():
    yield
    from feat import get_feat_manager
    from character_class import get_class_manager
    fm = get_feat_manager()
    for f in list(fm.feats):
        if f.name.startswith(PREFIX):
            fm.delete_feat(f.name)
    cm = get_class_manager()
    for c in list(cm.classes):
        if c.name.startswith(PREFIX):
            cm.delete_class(c.name)


def stored(name):
    from feat import get_feat_manager
    return get_feat_manager().get_feat(f"{PREFIX} {name}")


def test_a_mention_of_something_in_a_later_file_is_linked_at_the_end():
    first = {"feats": [feat("Alpha", f"While you have {PREFIX} Beta you also gain this.")]}
    second = {"feats": [feat("Beta")]}
    report = import_in_a_row(first, second)
    assert f"[[feat:{PREFIX} Beta]]" in stored("Alpha").description
    assert report.late_links == 1 and report.links_added >= 1
    assert report.imported == 2                                  # re-storing the text doesn't count as an import
    assert any("later file" in line for line in report.summary_lines())


def test_mentions_stay_plain_when_linking_is_off():
    first = {"feats": [feat("Alpha", f"While you have {PREFIX} Beta you also gain this.")]}
    second = {"feats": [feat("Beta")]}
    report = import_in_a_row(first, second, link_mentions=False)
    assert "[[" not in stored("Alpha").description
    assert report.late_links == 0


def test_a_mention_in_the_same_file_is_linked_straight_away_and_only_once():
    both = {"feats": [feat("Alpha", f"While you have {PREFIX} Beta you also gain this."), feat("Beta")]}
    report = content_io.import_bundle(both)
    assert stored("Alpha").description.count(f"[[feat:{PREFIX} Beta]]") == 1
    assert report.late_links == 0 and not report.imported_records
    # the final step must not link what is already linked
    content_io.finalize_link_check(report)
    assert stored("Alpha").description.count("[[") == 1


def test_the_final_step_changes_nothing_when_there_is_nothing_to_link():
    report = import_in_a_row({"feats": [feat("Alpha")]}, {"feats": [feat("Beta")]})
    assert report.late_links == 0
    assert stored("Alpha").description == "Plain."


def test_an_official_entry_is_never_touched_by_the_final_step():
    from feat import get_feat_manager
    official = next(f for f in get_feat_manager().feats if f.is_official and not f.is_custom)
    before = official.description
    bundle = {"feats": [{"name": official.name, "description": f"Mentions {PREFIX} Beta.", "type": "General"}]}
    report = import_in_a_row(bundle, {"feats": [feat("Beta")]})
    assert any(s[1] == official.name for s in report.skipped)
    assert get_feat_manager().get_feat(official.name).description == before


def test_a_link_to_something_that_never_arrives_is_still_reported():
    report = import_in_a_row({"feats": [feat("Alpha", f"See [[feat:{PREFIX} Missing]].")]},
                             {"feats": [feat("Beta")]})
    assert any(f"{PREFIX} Missing" in w for w in report.warnings)


def test_a_link_to_something_in_a_later_file_is_not_reported():
    report = import_in_a_row({"feats": [feat("Alpha", f"See [[feat:{PREFIX} Beta]].")]}, {"feats": [feat("Beta")]})
    assert not any(f"{PREFIX} Beta" in w for w in report.warnings)


def subclass(name="Path", parent="Class"):
    return {"name": f"{PREFIX} {name}", "parent_class": f"{PREFIX} {parent}", "description": "A path."}


def klass(name="Class"):
    return {"name": f"{PREFIX} {name}", "description": "A class.", "hit_die": 8}


def test_a_subclass_whose_class_arrives_in_a_later_file_is_added_at_the_end():
    from character_class import get_class_manager
    report = import_in_a_row({"subclasses": [subclass()]}, {"classes": [klass()]})
    cls = get_class_manager().get_class(f"{PREFIX} Class")
    assert cls is not None and [s.name for s in cls.subclasses] == [f"{PREFIX} Path"]
    assert not [s for s in report.skipped if s[0] == "subclasses"]
    assert report.added["subclasses"] == 1 and report.added["classes"] == 1
    assert not report.retry_subclasses


def test_a_subclass_whose_class_never_arrives_stays_skipped():
    report = import_in_a_row({"subclasses": [subclass()]}, {"feats": [feat("Beta")]})
    assert [s[1] for s in report.skipped if s[0] == "subclasses"] == [f"{PREFIX} Path"]
    assert report.added["subclasses"] == 0


def test_the_order_of_the_files_does_not_matter_for_subclasses():
    from character_class import get_class_manager
    import_in_a_row({"classes": [klass()]}, {"subclasses": [subclass()]})
    cls = get_class_manager().get_class(f"{PREFIX} Class")
    assert [s.name for s in cls.subclasses] == [f"{PREFIX} Path"]


def test_reports_merge_their_pending_work():
    a, b = content_io.ImportReport(), content_io.ImportReport()
    a.imported_records.append(("feats", {"name": "x"}))
    b.imported_records.append(("feats", {"name": "y"}))
    b.late_links = 2
    b.retry_subclasses.append({"name": "z"})
    a.merge(b)
    assert len(a.imported_records) == 2 and a.late_links == 2 and a.retry_subclasses == [{"name": "z"}]
