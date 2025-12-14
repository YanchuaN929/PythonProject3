from ui_copy import format_tsv


def test_format_tsv_basic():
    text = format_tsv(["A", "B"], [["1", "2"], ["3", "4"]])
    assert text == "A\tB\n1\t2\n3\t4"


def test_format_tsv_handles_none_and_non_str():
    text = format_tsv(["A"], [[None], [123]])
    assert text == "A\n\n123"


