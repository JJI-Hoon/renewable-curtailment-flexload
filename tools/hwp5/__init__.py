"""의존성 없이 HWP 5.0 문서를 읽고 최소 변경으로 편집하는 도구."""

from .cfb import CFB
from .container import replace_stream
from .records import (
    PARA_HEADER,
    PARA_TEXT,
    compress_section,
    decode_text,
    decompress_section,
    encode_text,
    parse,
    replace_paragraphs,
    serialize,
)

__all__ = [
    "CFB",
    "PARA_HEADER",
    "PARA_TEXT",
    "compress_section",
    "decode_text",
    "decompress_section",
    "encode_text",
    "extract_text",
    "fill_form",
    "parse",
    "replace_paragraphs",
    "replace_stream",
    "serialize",
]


def _sections(cfb: "CFB") -> list[dict]:
    secs = [e for e in cfb.entries() if e["name"].startswith("Section")]
    return sorted(secs, key=lambda e: int(e["name"][7:] or 0))


def extract_text(path: str) -> str:
    """HWP 본문 텍스트를 뽑아낸다."""
    cfb = CFB(path)
    root = cfb.root()
    compressed = bool(cfb.read(cfb.find("FileHeader"), root)[36] & 1)

    chunks = []
    for sec in _sections(cfb):
        raw = cfb.read(sec, root)
        if compressed:
            raw = decompress_section(raw)
        chunks += [
            decode_text(r["data"]) for r in parse(raw) if r["tag"] == PARA_TEXT
        ]
    return "\n".join(chunks)


def fill_form(src: str, out: str, replacements: dict[str, str]) -> dict:
    """서식 HWP의 안내 문구를 실제 내용으로 바꿔 새 파일로 저장한다.

    replacements의 key는 원본 문단에 들어 있는 고유 문구(부분 일치)다.
    반환값에 매칭 실패한 key(`missed`)가 담기므로 반드시 확인할 것.
    """
    cfb = CFB(src)
    section = cfb.find("Section0")
    records = parse(decompress_section(cfb.read(section, cfb.root())))

    missed = replace_paragraphs(records, replacements)
    payload = compress_section(serialize(records))
    result = replace_stream(src, "Section0", payload, out)
    result["missed"] = missed
    return result
