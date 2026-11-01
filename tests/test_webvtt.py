import datetime as dt

import pytest

from isubrip.subtitle_formats.subtitles import RTL_CHAR
from isubrip.subtitle_formats.webvtt import WebVTTCaptionBlock, WebVTTSubtitles


def make_caption(payload: str, settings: str = "") -> WebVTTCaptionBlock:
    return WebVTTCaptionBlock(
        start_time=dt.time(0, 0, 1),
        end_time=dt.time(0, 0, 2),
        payload=payload,
        settings=settings,
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("REGISTRERA &amp; RAPPORTERA", "REGISTRERA & RAPPORTERA"),
        ("&quot;Caf&eacute;&quot; &apos;menu&apos;", "\"Caf\u00e9\" 'menu'"),
        ("&#38; &#x26;", "& &"),
        ("&amp;amp; &amp;lt; &amp;#38;", "&amp; &lt; &#38;"),
        ("Plain text & a bare ampersand", "Plain text & a bare ampersand"),
        ("  one  &amp;\ttwo\nthree&nbsp; ", "  one  &\ttwo\nthree\u00a0 "),
    ],
)
def test_to_srt_decodes_character_references_once(payload: str, expected: str) -> None:
    caption = make_caption(payload)

    assert caption.to_srt().payload == expected


@pytest.mark.parametrize(
    ("alignment_enabled", "settings", "prefix", "expected_prefix"),
    [
        (False, "line:0%", "", ""),
        (True, "line:100%", "", ""),
        (True, "line:0%", RTL_CHAR, RTL_CHAR + r"{\an8}"),
        (True, "line:0%", "&#x202b;", RTL_CHAR + r"{\an8}"),
    ],
)
def test_to_srt_preserves_alignment_after_decoding(
    monkeypatch: pytest.MonkeyPatch,
    alignment_enabled: bool,
    settings: str,
    prefix: str,
    expected_prefix: str,
) -> None:
    monkeypatch.setattr(WebVTTCaptionBlock, "subrip_alignment_conversion", alignment_enabled)
    caption = make_caption(prefix + "Fish &amp; chips", settings=settings)

    assert caption.to_srt().payload == expected_prefix + "Fish & chips"


def test_to_srt_serializes_decoded_cues_without_changing_webvtt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(WebVTTCaptionBlock, "subrip_alignment_conversion", True)
    raw = (
        b"WEBVTT\r\n\r\n"
        b"NOTE conversion test\r\n\r\n"
        b"first-cue\r\n"
        b"00:00:01.000 --> 00:00:02.000 line:0%\r\n"
        b"<i>Fish &amp; chips</i>\r\n"
        b"Second&nbsp;line\r\n\r\n"
        b"second-cue\r\n"
        b"00:00:03.000 --> 00:00:04.000\r\n"
        b"Caf&#233; &amp;amp;\r\n"
    )
    subtitles = WebVTTSubtitles(data=raw, language_code="en")
    original_blocks = [str(block) for block in subtitles.blocks]
    expected = (
        "1\n00:00:01,000 --> 00:00:02,000\n"
        "{\\an8}<i>Fish & chips</i>\n"
        "Second\u00a0line\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\n"
        "Caf\u00e9 &amp;"
    ).encode("utf-8")

    assert subtitles.to_srt().dump() == expected
    assert [str(block) for block in subtitles.blocks] == original_blocks
    assert subtitles.dump() == raw
    assert subtitles.to_srt().dump() == expected
