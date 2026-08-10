"""HWP 5.0 BodyText 레코드 파싱과 문단 텍스트 조작.

레코드 헤더는 4바이트 정수 하나다.
    tag  = h & 0x3FF          레코드 종류
    level= (h >> 10) & 0x3FF  트리 깊이
    size = (h >> 20) & 0xFFF  본문 길이, 0xFFF이면 뒤에 UINT32 확장 길이가 붙는다
"""

from __future__ import annotations

import struct
import zlib

PARA_HEADER = 66
PARA_TEXT = 67
PARA_CHAR_SHAPE = 68
PARA_LINE_SEG = 69

# 확장 제어문자 — 본문에서 8개 wchar(16바이트)를 차지한다
EXTENDED_CONTROLS = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}

PARA_END = 0x000D
LINE_BREAK = 0x000A

# PARA_HEADER 필드 오프셋 — 실제 파일에서 선언값과 레코드 크기를 대조해 확인한 값
OFF_NCHARS = 0
OFF_NCHARSHAPES = 12
OFF_NRANGETAGS = 14
OFF_NLINESEGS = 16


def parse(blob: bytes) -> list[dict]:
    records, pos = [], 0
    while pos + 4 <= len(blob):
        header = struct.unpack_from("<I", blob, pos)[0]
        pos += 4
        tag = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            size = struct.unpack_from("<I", blob, pos)[0]
            pos += 4
        records.append({"tag": tag, "level": level, "data": blob[pos : pos + size]})
        pos += size
    return records


def serialize(records: list[dict]) -> bytes:
    out = bytearray()
    for r in records:
        tag, level, data = r["tag"], r["level"], r["data"]
        if len(data) < 0xFFF:
            out += struct.pack("<I", (tag & 0x3FF) | ((level & 0x3FF) << 10) | (len(data) << 20))
        else:
            out += struct.pack("<I", (tag & 0x3FF) | ((level & 0x3FF) << 10) | (0xFFF << 20))
            out += struct.pack("<I", len(data))
        out += data
    return bytes(out)


def decode_text(data: bytes) -> str:
    s, i = "", 0
    while i + 1 < len(data):
        ch = struct.unpack_from("<H", data, i)[0]
        if ch in EXTENDED_CONTROLS:
            i += 16
        elif ch < 32:
            i += 2
        else:
            s += chr(ch)
            i += 2
    return s


def encode_text(text: str) -> bytes:
    """문단 텍스트를 인코딩한다.

    모든 PARA_TEXT는 문단 끝 문자(0x0D)로 끝나야 한다.
    이게 빠지면 한글이 파일을 열지 못한다 — 가장 흔한 실수.
    """
    body = b"".join(
        struct.pack("<H", LINE_BREAK if ch == "\n" else ord(ch)) for ch in text
    )
    return body + struct.pack("<H", PARA_END)


def set_char_count(records: list[dict], header_index: int, count: int) -> None:
    """PARA_HEADER의 글자 수를 갱신한다. 상위 플래그 비트는 보존한다."""
    ph = bytearray(records[header_index]["data"])
    flag = struct.unpack_from("<I", ph, OFF_NCHARS)[0] & 0x80000000
    struct.pack_into("<I", ph, OFF_NCHARS, (count & 0x7FFFFFFF) | flag)
    records[header_index]["data"] = bytes(ph)


def unify_char_shape(records: list[dict], header_index: int, text_index: int) -> int | None:
    """문단의 글자모양 구간을 하나로 합친다.

    원본 서식이 여러 구간(위첨자 등)으로 나뉘어 있으면, 텍스트를 교체했을 때
    그 서식이 엉뚱한 글자에 걸린다. 위치 0의 shapeId 하나로 통일한다.
    LINE_SEG은 건드리지 않는다 — 손대면 파일이 깨진다.
    """
    for j in range(text_index + 1, min(text_index + 4, len(records))):
        if records[j]["tag"] != PARA_CHAR_SHAPE:
            continue
        cs = records[j]["data"]
        if len(cs) < 8:
            return None
        base = struct.unpack_from("<I", cs, 4)[0]
        if len(cs) == 8:
            return base
        records[j]["data"] = struct.pack("<II", 0, base)
        ph = bytearray(records[header_index]["data"])
        struct.pack_into("<H", ph, OFF_NCHARSHAPES, 1)
        records[header_index]["data"] = bytes(ph)
        return base
    return None


def header_index_of(records: list[dict], text_index: int) -> int:
    i = text_index
    while records[i]["tag"] != PARA_HEADER:
        i -= 1
    return i


def replace_paragraphs(records: list[dict], replacements: dict[str, str]) -> list[str]:
    """문단 텍스트에 key가 포함된 첫 문단을 value로 교체한다.

    반환값은 매칭에 실패한 key 목록.
    """
    missed = []
    for needle, value in replacements.items():
        hits = [
            i
            for i, r in enumerate(records)
            if r["tag"] == PARA_TEXT and needle in decode_text(r["data"])
        ]
        if not hits:
            missed.append(needle)
            continue
        ti = hits[0]
        hi = header_index_of(records, ti)
        records[ti]["data"] = encode_text(value)
        set_char_count(records, hi, len(value) + 1)
        unify_char_shape(records, hi, ti)
    return missed


def decompress_section(blob: bytes) -> bytes:
    """Section 스트림은 헤더 없는 raw deflate로 압축돼 있다."""
    return zlib.decompress(blob, -15)


def compress_section(blob: bytes) -> bytes:
    return zlib.compress(blob, 9)[2:-4]
