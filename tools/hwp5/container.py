"""수정한 Section 스트림을 원본 HWP에 최소 변경으로 되돌려 쓴다.

CFB 컨테이너를 처음부터 다시 쓰는 방식은 구조상 맞아도 한글이 열지 못했다.
그래서 **원본 바이트를 그대로 두고 파일 끝에 섹터를 덧붙인 뒤
FAT과 디렉터리 엔트리만 고치는** 방식을 쓴다. 실제로 바뀌는 바이트는 37개뿐이다.
"""

from __future__ import annotations

import struct

SECTOR_SIZE = 512
END_OF_CHAIN = 0xFFFFFFFE
MAXREGSECT = 0xFFFFFFF0


def replace_stream(src: str, stream_name: str, payload: bytes, out: str) -> dict:
    with open(src, "rb") as fh:
        d = bytearray(fh.read())

    ssz = 1 << struct.unpack_from("<H", d, 30)[0]
    if ssz != SECTOR_SIZE:
        raise ValueError(f"512바이트 섹터만 지원 (현재 {ssz})")

    fat_sector_count = struct.unpack_from("<I", d, 44)[0]
    dir_start = struct.unpack_from("<I", d, 48)[0]
    mini_cutoff = struct.unpack_from("<I", d, 56)[0]
    used_sectors = (len(d) - SECTOR_SIZE) // ssz
    difat = [x for x in struct.unpack_from("<109I", d, 76) if x < MAXREGSECT]

    def fat_offset(i: int) -> int:
        return (difat[i // (ssz // 4)] + 1) * ssz + (i % (ssz // 4)) * 4

    def fat_get(i: int) -> int:
        return struct.unpack_from("<I", d, fat_offset(i))[0]

    def fat_set(i: int, v: int) -> None:
        struct.pack_into("<I", d, fat_offset(i), v)

    # 미니스트림 임계값보다 작으면 판독기가 미니FAT을 찾는다.
    # 0으로 패딩해 일반 섹터 경로를 타게 만든다 (raw deflate는 뒤쪽 0을 무시).
    declared_size = len(payload)
    if declared_size < mini_cutoff:
        payload = payload + b"\0" * (mini_cutoff - declared_size)
        declared_size = len(payload)

    needed = -(-len(payload) // ssz)
    capacity = fat_sector_count * (ssz // 4)
    if used_sectors + needed > capacity:
        raise ValueError(f"FAT 여유 부족: 필요 {needed}, 여유 {capacity - used_sectors}")

    first = used_sectors
    d += payload + b"\0" * (needed * ssz - len(payload))
    for k in range(needed):
        fat_set(first + k, END_OF_CHAIN if k == needed - 1 else first + k + 1)

    # 디렉터리 체인을 따라가며 대상 엔트리의 start/size만 갱신
    chain, s, seen = [], dir_start, set()
    while s < MAXREGSECT and s not in seen:
        seen.add(s)
        chain.append(s)
        s = fat_get(s)

    patched = False
    for sector in chain:
        base = (sector + 1) * ssz
        for e in range(ssz // 128):
            off = base + e * 128
            nlen = struct.unpack_from("<H", d, off + 64)[0]
            if nlen < 2:
                continue
            if d[off : off + nlen - 2].decode("utf-16-le", "ignore") == stream_name:
                struct.pack_into("<I", d, off + 116, first)
                struct.pack_into("<Q", d, off + 120, declared_size)
                patched = True
    if not patched:
        raise ValueError(f"디렉터리에서 {stream_name} 엔트리를 찾지 못함")

    with open(out, "wb") as fh:
        fh.write(bytes(d))

    return {"bytes": len(d), "first_sector": first, "sectors_used": needed}
