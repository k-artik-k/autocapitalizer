from whatsapp_capitalize import autocorrect
from whatsapp_capitalize.sentence_engine import Typist, VK_BACK, VK_RETURN


TEXT_KEY = 0  # Text behavior is driven by ``ch``; platform key codes are only needed for controls.


def type_text(typist, text):
    return [typist.process(TEXT_KEY, character) for character in text]


def test_capitalizes_the_start_of_messages_and_sentences():
    typist = Typist()

    plans = type_text(typist, "hello. world")

    assert [plan.text for plan in plans if plan] == ["H", "W"]


def test_does_not_end_a_sentence_after_known_abbreviations():
    typist = Typist()

    plans = type_text(typist, "e.g. this")

    assert [plan.text for plan in plans if plan] == ["E"]


def test_corrects_a_word_and_allows_immediate_undo():
    typist = Typist()
    type_text(typist, "dont")

    correction = typist.process(TEXT_KEY, " ")
    undo = typist.process(VK_BACK, "")

    assert correction.text == "Don't "
    assert correction.backspaces == 4
    assert undo.text == "Dont"
    assert undo.backspaces == len("Don't") + 1


def test_custom_corrections_reload_when_the_file_changes(tmp_path):
    autocorrect.set_folder(tmp_path)
    (tmp_path / "my_corrections.txt").write_text("omw = on my way\n", encoding="utf-8")
    typist = Typist()
    type_text(typist, "omw")

    plan = typist.process(TEXT_KEY, " ")

    assert plan.text == "On my way "
    assert plan.backspaces == 3


def test_enter_corrects_a_word_and_keeps_the_enter_key():
    typist = Typist()
    type_text(typist, "cant")

    plan = typist.process(VK_RETURN, "")

    assert plan.text == "Can't"
    assert plan.backspaces == 4
    assert plan.vk_after == VK_RETURN
