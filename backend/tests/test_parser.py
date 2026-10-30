import pytest

from app.parser import ParseError, parse_lines, solution


@pytest.mark.parametrize("source,stress", [
    ("Дерево", 1), ("Собака", 3), ("Остановка", 5), ("каталОг", 5),
    ("тОрт", 1), ("А́рка", 0), ("молоко", 5), ("берёза", 3),
    ("свекла", 2), ("дом", 1),
])
def test_stress(source, stress):
    item = parse_lines(source, "stress")[0]
    assert item["data"]["stress"] == stress
    assert not item["needs_review"]


@pytest.mark.parametrize("word", [
    "замок", "Замок", "мука", "муку", "коса", "парит", "отзыв", "атлас",
    "ирис", "орган", "начала", "плачу", "неизвестноеслово", "бутявковед",
])
def test_unknown_and_homographs_need_review(word):
    item = parse_lines(word, "stress")[0]
    assert item["needs_review"]
    assert item["data"]["stress"] is None


@pytest.mark.parametrize("source,stress", [
    ("замОк", 3), ("мУка", 1), ("мукА", 3), ("косА", 3),
    ("бутявковЕд", 8), ("деревО", 5),
])
def test_manual_stress_has_priority(source, stress, monkeypatch):
    def unexpected_lookup(word):
        pytest.fail("Explicit stress must not invoke automatic accentuation")

    monkeypatch.setattr("app.parser.automatic_stress", unexpected_lookup)
    item = parse_lines(source, "stress")[0]
    assert item["data"]["stress"] == stress
    assert not item["needs_review"]


@pytest.mark.parametrize("variants", [
    [], [["молоко"]], [["моло+ко+"]], [["+молоко"]], [["м+олоко"]],
    [["молока+"]], [["молоко+лишнее"]], [["мо+локо"], ["молоко+"]],
])
def test_invalid_automatic_results_need_review(variants, monkeypatch):
    from app import stress

    class FakeAccentor:
        def do_accents(self, words):
            return variants

    stress.automatic_stress.cache_clear()
    monkeypatch.setattr(stress, "_accentor", lambda: FakeAccentor())
    try:
        assert parse_lines("молоко", "stress")[0]["needs_review"]
    finally:
        stress.automatic_stress.cache_clear()


def test_accentor_is_offline_shared_and_results_are_cached(monkeypatch):
    from app import stress

    calls = []

    class FakeAccentor:
        def __init__(self, **options):
            calls.append(options)

        def do_accents(self, words):
            calls.append(words)
            raise ValueError("Unknown or ambiguous word")

    stress._accentor.cache_clear()
    stress.automatic_stress.cache_clear()
    monkeypatch.setattr(stress, "Accentor", FakeAccentor)
    try:
        assert stress.automatic_stress("бутявковед") is None
        assert stress.automatic_stress("бутявковед") is None
        assert stress.automatic_stress("замок") is None
        assert calls == [
            {"mode": "one", "exception_for_unknown": True, "use_wiki": False},
            [["бутявковед"]], [["замок"]],
        ]
    finally:
        stress._accentor.cache_clear()
        stress.automatic_stress.cache_clear()


def test_spelling_multi_gap_and_empty_variants():
    entries = parse_lines("мыш(ь,)\nопас(,т)ный\nс(ло,ла)в(о,а,и,е)", "spelling")
    assert entries[0]["data"]["parts"][1]["options"] == ["ь", ""]
    assert entries[1]["data"]["parts"][1]["correct"] == ""
    assert solution(entries[1]["data"]) == "опасный"
    assert solution(entries[2]["data"]) == "слово"


def test_grammar_and_bom():
    item = parse_lines("\ufeffОн (сберечь|сбережёт,сберегёт) здоровье.", "grammar")[0]
    assert item["data"]["parts"][1]["hint"] == "сберечь"
    assert solution(item["data"]) == "Он сбережёт здоровье."


def test_explanations_and_literal_spaces():
    item = parse_lines("[песочный] зАмок", "stress")[0]
    assert item["data"] == {"word": "замок", "stress": 1, "explanation": "песочный"}
    assert solution(item["data"]) == "за́мок"
    entries = parse_lines("По( ,)этому\n[причина] По(, )этому\nграм(,м)ота", "spelling")
    assert entries[0]["data"]["parts"][1]["options"] == [" ", ""]
    assert [solution(e["data"]) for e in entries] == ["По этому", "Поэтому", "грамота"]
    assert entries[1]["data"]["explanation"] == "причина"


def test_error_line_matches_raw_line_numbers():
    with pytest.raises(ParseError, match="Строка 4:"):
        parse_lines("\nдом\n\nдва слова", "stress")


@pytest.mark.parametrize("source", ["[] зАмок", "[песочный зАмок", "зАмок [песочный", "[[песочный]] зАмок"])
def test_invalid_explanations(source):
    with pytest.raises(ParseError):
        parse_lines(source, "stress")


@pytest.mark.parametrize("source", ["[песочный] зАмок", "зАмок [песочный]", "зА[песочный]мок"])
def test_stress_explanation_anywhere(source):
    item = parse_lines(source, "stress")[0]
    assert item["data"] == {"word": "замок", "stress": 1, "explanation": "песочный"}
    assert item["source"] == source


def test_explanations_inside_sentence_and_options():
    item = parse_lines("Он [о будущем] (сберечь|сбережёт[верная форма],сберегёт) здоровье. [контекст]", "grammar")[0]
    assert item["data"]["explanation"] == "о будущем; верная форма; контекст"
    assert solution(item["data"]) == "Он  сбережёт здоровье."
    item = parse_lines("грам(,[без удвоения]м)ота", "spelling")[0]
    assert solution(item["data"]) == "грамота"
    assert item["data"]["parts"][1]["options"] == ["", "м"]


@pytest.mark.parametrize("source,category", [
    ("", "stress"), ("дЕрЕво", "stress"), ("два слова", "stress"),
    ("мыш(ь)", "spelling"), ("мыш(ь,ь)", "spelling"), ("мыш(ь,", "spelling"),
    ("((а,б))", "spelling"), ("Он (сберечь,сбережёт)", "grammar"),
    ("Он (|сбережёт,сберегёт)", "grammar"), ("Он (быть|,был)", "grammar"),
])
def test_invalid_formats(source, category):
    with pytest.raises(ParseError):
        parse_lines(source, category)
