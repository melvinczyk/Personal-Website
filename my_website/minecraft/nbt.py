"""Minimal reader for Minecraft's NBT format (gzipped, big-endian).

Only what playerdata needs: the tag types, no writing. Vendored rather than
pulled in as a dependency so the portal has no runtime package to install.
"""

import gzip
import struct

TAG_END = 0


class _Reader:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0

    def take(self, n):
        chunk = self.buf[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def unpack(self, fmt, size):
        return struct.unpack(fmt, self.take(size))[0]

    def string(self):
        return self.take(self.unpack('>H', 2)).decode('utf-8', 'replace')


def _payload(r, tag):
    if tag == 1:  return r.unpack('>b', 1)
    if tag == 2:  return r.unpack('>h', 2)
    if tag == 3:  return r.unpack('>i', 4)
    if tag == 4:  return r.unpack('>q', 8)
    if tag == 5:  return r.unpack('>f', 4)
    if tag == 6:  return r.unpack('>d', 8)
    if tag == 7:  return list(r.take(r.unpack('>i', 4)))
    if tag == 8:  return r.string()
    if tag == 9:
        item_tag = r.unpack('>B', 1)
        return [_payload(r, item_tag) for _ in range(r.unpack('>i', 4))]
    if tag == 10:
        out = {}
        while True:
            child = r.unpack('>B', 1)
            if child == TAG_END:
                return out
            # the name has to be read before the payload: Python evaluates the
            # right-hand side of an assignment first
            name = r.string()
            out[name] = _payload(r, child)
    if tag == 11: return [r.unpack('>i', 4) for _ in range(r.unpack('>i', 4))]
    if tag == 12: return [r.unpack('>q', 8) for _ in range(r.unpack('>i', 4))]
    raise ValueError(f'unknown NBT tag {tag}')


def load(path):
    """Read a gzipped .dat file and return its root compound as a dict."""
    r = _Reader(gzip.open(path, 'rb').read())
    root = r.unpack('>B', 1)
    r.string()                      # root name, always empty in practice
    return _payload(r, root)
