"""The shared "add from pasted text" flow (ui/text_import_flow.py) and the pages that use it."""

import time
from tkinter import messagebox
from types import SimpleNamespace

import pytest

from ui.text_import_flow import announce_added, import_from_pasted_text


class Parsed:
    def __init__(self, name, review=(), uncertain=()):
        self.name, self._review, self._uncertain = name, list(review), list(uncertain)

    def needs_review(self):
        return self._review

    def uncertain_fields(self):
        return self._uncertain


class FakeOwner:
    def __init__(self):
        self.waited = []

    def winfo_toplevel(self):
        return "toplevel"

    def wait_window(self, window):
        self.waited.append(window)


def dialog_returning(result):
    class Dialog:
        def __init__(self, parent):
            self.parent, self.result = parent, result
    return Dialog


class Editor:
    def __init__(self, result):
        self.result = result


@pytest.fixture()
def boxes(monkeypatch):
    calls = {"error": [], "askyesno": [], "showinfo": []}
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **k: calls["error"].append((title, message)))
    monkeypatch.setattr(messagebox, "showinfo", lambda title, message, **k: calls["showinfo"].append((title, message)))
    answers = {"askyesno": True}
    monkeypatch.setattr(messagebox, "askyesno", lambda title, message, **k: calls["askyesno"].append((title, message))
                        or answers["askyesno"])
    calls["answers"] = answers
    return calls


def run(owner=None, parsed=(), saved=(), add=None, convert=None, **kw):
    """Run the flow; ``saved`` is what each editor returns in turn (None = cancelled)."""
    owner = owner or FakeOwner()
    results = iter(saved)
    opened = []

    def make_editor(draft, review, progress):
        opened.append((draft, review, progress))
        return Editor(next(results))

    parsed = list(parsed)
    added = import_from_pasted_text(
        owner, import_cls=dialog_returning(parsed or None),
        load_converter=lambda: (convert or (lambda p: SimpleNamespace(name=p.name))),
        noun="feat", noun_phrase="a feat", make_editor=make_editor,
        add=add or (lambda r: True), **kw)
    return added, opened, owner


def test_cancelling_the_paste_dialog_does_nothing(boxes):
    added, opened, owner = run(parsed=[])
    assert added == [] and opened == [] and len(owner.waited) == 1       # only the paste dialog was waited on


def test_each_draft_opens_in_the_editor_with_its_review_fields_and_progress(boxes):
    parsed = [Parsed("A", review=["name"], uncertain=["type", "name"]), Parsed("B"), Parsed("C")]
    saved = [SimpleNamespace(name="A"), SimpleNamespace(name="B"), SimpleNamespace(name="C")]
    added, opened, owner = run(parsed=parsed, saved=saved)
    assert added == ["A", "B", "C"]
    assert [(d.name, r, p) for d, r, p in opened] == [("A", ["name", "type"], "1 of 3"), ("B", [], "2 of 3"),
                                                      ("C", [], "3 of 3")]
    assert len(owner.waited) == 4                                         # the paste dialog and three editors


def test_a_single_draft_has_no_progress_label(boxes):
    _added, opened, _owner = run(parsed=[Parsed("Solo")], saved=[SimpleNamespace(name="Solo")])
    assert opened[0][2] == ""


def test_the_dialogs_belong_to_the_given_parent_or_the_toplevel(boxes):
    seen = []

    class Dialog:
        def __init__(self, parent):
            seen.append(parent)
            self.result = None
    import_from_pasted_text(FakeOwner(), import_cls=Dialog, load_converter=lambda: None, noun="feat",
                            noun_phrase="a feat", make_editor=None, add=None)
    import_from_pasted_text(FakeOwner(), import_cls=Dialog, load_converter=lambda: None, noun="feat",
                            noun_phrase="a feat", make_editor=None, add=None, dialog_parent="the page")
    assert seen == ["toplevel", "the page"]


def test_a_parser_that_cannot_be_loaded_is_reported_and_stops(boxes):
    def broken():
        raise ImportError("no parser")
    added = import_from_pasted_text(FakeOwner(), import_cls=dialog_returning([Parsed("A")]), load_converter=broken,
                                    noun="feat", noun_phrase="a feat", make_editor=None, add=None)
    assert added == []
    assert boxes["error"] == [("Auto-Detect Unavailable", "Could not load the text importer:\nno parser")]


def test_a_draft_that_cannot_be_built_is_reported_and_skipped(boxes):
    def convert(parsed):
        if parsed.name == "bad":
            raise ValueError("boom")
        return SimpleNamespace(name=parsed.name)
    added, opened, _owner = run(parsed=[Parsed("bad"), Parsed("good")], saved=[SimpleNamespace(name="good")],
                                convert=convert)
    assert added == ["good"] and len(opened) == 1
    assert boxes["error"] == [("Parse Error", "Could not build feat 1 of 2:\nboom")]


def test_a_duplicate_is_refused_with_a_message_and_not_counted(boxes):
    known = {"Taken"}
    added, _opened, _owner = run(
        parsed=[Parsed("Taken"), Parsed("Fresh")], saved=[SimpleNamespace(name="Taken"), SimpleNamespace(name="Fresh")],
        add=lambda r: r.name not in known)
    assert added == ["Fresh"]
    assert boxes["error"] == [("Error", "A feat named 'Taken' already exists. It was not added.")]


def test_prepare_touches_each_saved_result_before_it_is_added(boxes):
    order = []
    added, _opened, _owner = run(parsed=[Parsed("A")], saved=[SimpleNamespace(name="A")],
                                 prepare=lambda r: order.append(("prepare", r.name)),
                                 add=lambda r: order.append(("add", r.name)) or True)
    assert order == [("prepare", "A"), ("add", "A")] and added == ["A"]


def test_cancelling_an_editor_asks_whether_to_go_on(boxes):
    parsed = [Parsed("A"), Parsed("B"), Parsed("C")]
    added, opened, _owner = run(parsed=parsed, saved=[None, SimpleNamespace(name="B"), SimpleNamespace(name="C")])
    assert added == ["B", "C"] and len(opened) == 3
    assert boxes["askyesno"] == [("Continue?", "Skip this feat and continue reviewing the remaining 2 feat(s)?")]

    boxes["askyesno"].clear()
    boxes["answers"]["askyesno"] = False                                   # "no": stop reviewing
    added, opened, _owner = run(parsed=parsed, saved=[None])
    assert added == [] and len(opened) == 1


def test_cancelling_the_last_editor_does_not_ask(boxes):
    added, _opened, _owner = run(parsed=[Parsed("A")], saved=[None])
    assert added == [] and boxes["askyesno"] == []


def test_announce_added_only_speaks_for_several(boxes):
    announce_added(["One"], "feats")
    assert boxes["showinfo"] == []
    announce_added(["One", "Two"], "feats")
    assert boxes["showinfo"] == [("Feats Added", "Added 2 feats:\nOne\nTwo")]


# ---------------------------------------------------------------- the pages

def pump(root, n=12):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


def test_the_feats_page_adds_pasted_feats_and_marks_them_homebrew(tk_root, monkeypatch, boxes):
    import ui.feat_text_import as feat_import
    import ui.feats_view as feats_view
    import text_import.feat_parser as feat_parser
    from feat import Feat, get_feat_manager

    manager = get_feat_manager()
    view = feats_view.FeatsView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        monkeypatch.setattr(feat_import, "FeatTextImportDialog", dialog_returning([Parsed("T-Pasted", review=["prereq"])]))
        monkeypatch.setattr(feat_parser, "to_feat", lambda parsed: Feat(name=parsed.name, type="General"))
        opened = []

        class FakeEditor:
            def __init__(self, parent, title, prefill_feat=None, review_fields=None, batch_progress=""):
                opened.append((title, review_fields, batch_progress))
                self.result = Feat(name=prefill_feat.name, type="General", is_custom=False)

        monkeypatch.setattr(feats_view, "FeatEditorDialog", FakeEditor)
        view.wait_window = lambda w: None

        view._on_add_feat_from_text()
        assert opened == [("Review Feat: T-Pasted", ["prereq"], "")]
        stored = manager.get_feat("T-Pasted")
        assert stored is not None and stored.is_custom                    # prepare() marked it homebrew
        assert boxes["showinfo"] == [("Success", "Feat 'T-Pasted' added!")]
    finally:
        manager.delete_feat("T-Pasted")
        view.destroy()


def test_the_lineages_page_reloads_after_pasted_lineages_are_saved(tk_root, monkeypatch, boxes):
    import ui.lineage_text_import as lineage_import
    import ui.lineages_view as lineages_view
    import text_import.lineage_parser as lineage_parser
    from lineage import Lineage

    view = lineages_view.LineagesView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        monkeypatch.setattr(lineage_import, "LineageTextImportDialog",
                            dialog_returning([Parsed("T-One"), Parsed("T-Two")]))
        monkeypatch.setattr(lineage_parser, "to_lineage", lambda parsed: Lineage(name=parsed.name))
        titles = []

        class FakeEditor:
            def __init__(self, parent, manager, prefill_lineage=None, review_fields=None, batch_progress=""):
                titles.append((prefill_lineage.name, batch_progress))
                self.result = prefill_lineage                             # (the real editor stores it itself)

            def grab_set(self):
                pass

        monkeypatch.setattr(lineages_view, "LineageEditorDialog", FakeEditor)
        view.wait_window = lambda w: None
        reloads = []
        original = view._load_lineages
        view._load_lineages = lambda: (reloads.append(1), original())

        view._on_add_lineage_from_text()
        assert titles == [("T-One", "1 of 2"), ("T-Two", "2 of 2")]
        assert reloads == [1]
        assert boxes["showinfo"] == [("Lineages Added", "Added 2 lineages:\nT-One\nT-Two")]
    finally:
        view.destroy()
