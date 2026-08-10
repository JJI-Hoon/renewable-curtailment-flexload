"""MS-CFB(복합 문서) 리더 — 외부 의존성 없음.

olefile을 설치할 수 없는 환경에서 HWP 5.0 파일을 열기 위해 직접 구현했다.
512바이트 섹터, 64바이트 미니섹터, 4096바이트 미니스트림 임계값을 따른다.
"""

from __future__ import annotations

import struct

CFB_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
MAXREGSECT = 0xFFFFFFF0


class CFB:
    def __init__(self, path: str):
        with open(path, "rb") as fh:
            self.d = fh.read()
        if self.d[:8] != CFB_MAGIC:
            raise ValueError(f"{path}: CFB 시그니처가 아님")

        self.ssz = 1 << struct.unpack_from("<H", self.d, 30)[0]
        self.mssz = 1 << struct.unpack_from("<H", self.d, 32)[0]
        self.dir_start = struct.unpack_from("<I", self.d, 48)[0]
        self.mini_cutoff = struct.unpack_from("<I", self.d, 56)[0]
        self.minifat_start = struct.unpack_from("<I", self.d, 60)[0]
        self.difat_start = struct.unpack_from("<I", self.d, 68)[0]
        self._fat: list[int] | None = None
        self._minifat: list[int] | None = None

    def sector(self, n: int) -> bytes:
        off = (n + 1) * self.ssz
        return self.d[off : off + self.ssz]

    def _difat(self) -> list[int]:
        entries = list(struct.unpack_from("<109I", self.d, 76))
        s = self.difat_start
        while s < MAXREGSECT and s < len(self.d) // self.ssz:
            vals = struct.unpack_from("<%dI" % (self.ssz // 4), self.sector(s), 0)
            entries.extend(vals[:-1])
            s = vals[-1]
        return [e for e in entries if e < MAXREGSECT]

    @property
    def fat(self) -> list[int]:
        if self._fat is None:
            table: list[int] = []
            for fs in self._difat():
                table.extend(struct.unpack_from("<%dI" % (self.ssz // 4), self.sector(fs), 0))
            self._fat = table
        return self._fat

    @property
    def minifat(self) -> list[int]:
        if self._minifat is None:
            b = self.read_chain(self.minifat_start)
            self._minifat = list(struct.unpack_from("<%dI" % (len(b) // 4), b, 0))
        return self._minifat

    def chain(self, start: int) -> list[int]:
        out, s, seen = [], start, set()
        while s < MAXREGSECT and s not in seen:
            seen.add(s)
            out.append(s)
            s = self.fat[s] if s < len(self.fat) else 0xFFFFFFFE
        return out

    def read_chain(self, start: int, size: int | None = None) -> bytes:
        b = b"".join(self.sector(s) for s in self.chain(start))
        return b[:size] if size else b

    def entries(self) -> list[dict]:
        b = self.read_chain(self.dir_start)
        out = []
        for i in range(0, len(b), 128):
            e = b[i : i + 128]
            if len(e) < 128:
                break
            nlen = struct.unpack_from("<H", e, 64)[0]
            if nlen < 2:
                continue
            out.append(
                {
                    "index": i // 128,
                    "name": e[: nlen - 2].decode("utf-16-le", "ignore"),
                    "type": e[66],
                    "start": struct.unpack_from("<I", e, 116)[0],
                    "size": struct.unpack_from("<Q", e, 120)[0],
                }
            )
        return out

    def root(self) -> dict:
        return next(e for e in self.entries() if e["type"] == 5)

    def read(self, entry: dict, root: dict | None = None) -> bytes:
        """스트림 내용을 읽는다. 4096바이트 미만이면 미니FAT 경로를 탄다."""
        root = root or self.root()
        if entry["size"] < self.mini_cutoff and entry["name"] != "Root Entry":
            ministream = self.read_chain(root["start"], root["size"])
            out, s, seen = b"", entry["start"], set()
            while s < MAXREGSECT and s not in seen:
                seen.add(s)
                out += ministream[s * self.mssz : (s + 1) * self.mssz]
                s = self.minifat[s] if s < len(self.minifat) else 0xFFFFFFFE
            return out[: entry["size"]]
        return self.read_chain(entry["start"], entry["size"])

    def find(self, name: str) -> dict:
        return next(e for e in self.entries() if e["name"] == name)
