"""The "add it by hand, or paste text for auto-detect" dialogs shared by the collections (ui/text_import_dialogs.py)."""

import importlib
import time
from tkinter import messagebox

import pytest

# collection -> (module, source dialog, paste dialog, a block of text its parser understands, how many it holds)
KINDS = {
    "feat": ("ui.feat_text_import", "AddFeatSourceDialog", "FeatTextImportDialog", 2,
             "Alert\nOrigin Feat\nPrerequisite: None\nYou gain the following benefits:\nInitiative Proficiency. "
             "You can add your proficiency bonus to your initiative rolls.\n\nTough\nOrigin Feat\n"
             "Your hit point maximum increases."),
    "equipment": ("ui.equipment_text_import", "AddEquipmentSourceDialog", "EquipmentTextImportDialog", 2,
                  "Longsword\nType: Melee Weapon\nCost: 15 gp\nWeight: 3 lb\nA blade.\n\nRope\nCost: 1 gp\n"
                  "Weight: 10 lb\nHemp rope."),
    "lineage": ("ui.lineage_text_import", "AddLineageSourceDialog", "LineageTextImportDialog", 1,
                "Changeling\nCreature Type: Fey\nSize: Medium\nSpeed: 30 feet\nShifty folk.\n\n"
                "Shape-Shifter. As an action you change."),
    "magic_item": ("ui.magic_item_text_import", "AddMagicItemSourceDialog", "MagicItemTextImportDialog", 2,
                   "Bag of Holding\nWondrous item, uncommon\nAn extradimensional bag.\n\nRing of Protection\n"
                   "Ring, rare (requires attunement)\nYou gain a +1 bonus."),
    "spell": ("ui.spell_text_import", "AddSpellSourceDialog", "SpellTextImportDialog", 1,
              "Fire Bolt\nEvocation Cantrip\nCasting Time: 1 Action\nRange: 120 feet\nComponents: V, S\n"
              "Duration: Instantaneous\nClasses: Sorcerer, Wizard\nYou hurl a mote of fire."),
}


def pump(root, n=6):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


@pytest.fixture(params=list(KINDS))
def kind(request):
    module, add_name, import_name, count, sample = KINDS[request.param]
    mod = importlib.import_module(module)
    return SimpleKind(request.param, getattr(mod, add_name), getattr(mod, import_name), count, sample)


class SimpleKind:
    def __init__(self, name, add_cls, import_cls, count, sample):
        self.name, self.add_cls, self.import_cls, self.count, self.sample = name, add_cls, import_cls, count, sample


@pytest.fixture()
def boxes(monkeypatch):
    calls = []
    monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **kw: calls.append(("warning", title, message)))
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: calls.append(("error", title, message)))
    return calls


def test_every_spec_is_complete_and_names_a_real_parser(kind):
    spec = kind.add_cls.SPEC
    assert spec is kind.import_cls.SPEC
    for field in ("add_title", "add_question", "add_blurb", "import_title", "paste_heading", "paste_help",
                  "disclaimer", "placeholder", "detected_unit", "empty_warning", "retry_hint", "nothing_found"):
        assert getattr(spec, field).strip(), field
    parser = importlib.import_module(spec.parser_module)
    assert callable(parser.split_blocks) and callable(getattr(parser, spec.parse_function))


def test_the_source_dialog_answers_manual_auto_or_nothing(kind, tk_root):
    for choose, expected in (("_choose_manual", "manual"), ("_choose_auto", "auto"), ("_cancel", None)):
        dialog = kind.add_cls(tk_root)
        pump(tk_root)
        assert dialog.title() == kind.add_cls.SPEC.add_title
        getattr(dialog, choose)()
        assert dialog.result == expected


def test_pasted_text_is_counted_and_parsed(kind, tk_root, boxes):
    dialog = kind.import_cls(tk_root)
    pump(tk_root)
    try:
        assert dialog.title() == kind.import_cls.SPEC.import_title
        assert dialog._placeholder_active

        dialog._preview()                                   # nothing but the placeholder yet
        assert dialog._status.cget("text") == "Nothing to parse yet."
        dialog._detect()
        assert boxes == [("warning", "No Text", kind.import_cls.SPEC.empty_warning)]
        boxes.clear()

        dialog._clear_placeholder()                         # clicking into the box clears the example
        assert not dialog._placeholder_active and dialog._get_text() == ""

        dialog._text.insert("1.0", kind.sample)
        dialog._preview()
        unit = kind.import_cls.SPEC.detected_unit
        assert dialog._status.cget("text") == f"Detected {kind.count} {unit}{'s' if kind.count != 1 else ''}."

        dialog._detect()
        assert boxes == [] and dialog.result and len(dialog.result) == kind.count
        assert all((p.get("name") or "").strip() for p in dialog.result)
    finally:
        try:
            dialog.destroy()
        except Exception:
            pass


def test_text_with_nothing_in_it_is_refused_politely(kind, tk_root, boxes):
    dialog = kind.import_cls(tk_root)
    pump(tk_root)
    try:
        dialog._clear_placeholder()
        dialog._text.insert("1.0", "   \n\n  ")
        dialog._detect()                                    # whitespace only: same as empty
        assert boxes[0][:2] == ("warning", "No Text")
        boxes.clear()
    finally:
        dialog._cancel()
    assert dialog.result is None


def test_a_parser_that_blows_up_does_not_kill_the_dialog(kind, tk_root, boxes, monkeypatch):
    parser = importlib.import_module(kind.import_cls.SPEC.parser_module)

    def boom(text):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(parser, kind.import_cls.SPEC.parse_function, boom)
    dialog = kind.import_cls(tk_root)
    pump(tk_root)
    try:
        dialog._clear_placeholder()
        dialog._text.insert("1.0", kind.sample)
        dialog._detect()
        (level, title, message), = boxes
        assert level == "error" and title == "Could Not Parse"
        assert "kaboom" in message and message.endswith(kind.import_cls.SPEC.retry_hint)
        assert dialog.result is None and dialog.winfo_exists()
    finally:
        dialog.destroy()


def test_a_parse_with_no_usable_blocks_says_nothing_was_detected(kind, tk_root, boxes, monkeypatch):
    parser = importlib.import_module(kind.import_cls.SPEC.parser_module)
    monkeypatch.setattr(parser, kind.import_cls.SPEC.parse_function, lambda text: [{"name": " ", "description": ""}])
    dialog = kind.import_cls(tk_root)
    pump(tk_root)
    try:
        dialog._clear_placeholder()
        dialog._text.insert("1.0", "something")
        dialog._detect()
        assert boxes == [("warning", "Nothing Detected", kind.import_cls.SPEC.nothing_found)]
        assert dialog.result is None
    finally:
        dialog.destroy()
