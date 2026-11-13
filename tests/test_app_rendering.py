from app import answer_markdown, plain_text_markdown


def test_answer_markdown_keeps_formatting_but_escapes_tilde_and_dollar() -> None:
    text = "**통상 3~4일** 이내\n- 문의: 044-201-8242~8251\n- 금액 $10"

    rendered = answer_markdown(text)

    assert "**통상 3\\~4일**" in rendered          # 굵게는 유지, 범위 표기는 취소선이 되지 않게
    assert "8242\\~8251" in rendered
    assert "\\$10" in rendered                      # 수식으로 해석되지 않게
    assert rendered.count("- ") == 2                # 목록은 유지


def test_answer_markdown_does_not_double_escape() -> None:
    assert answer_markdown("이미 \\~ 처리") == "이미 \\~ 처리"


def test_plain_text_markdown_shows_faq_text_as_is() -> None:
    rendered = plain_text_markdown("- 1.28.~1.30. *주의* [링크](x) #해시 <b>굵게</b>")

    assert rendered == "\\- 1.28.\\~1.30. \\*주의\\* \\[링크\\]\\(x\\) \\#해시 \\<b\\>굵게\\</b\\>"


def test_plain_text_markdown_escapes_numbered_list_at_line_start() -> None:
    assert plain_text_markdown("1. 첫째\n2. 둘째") == "1\\. 첫째\n2\\. 둘째"
