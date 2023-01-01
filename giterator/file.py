import tarfile
from typing import Dict, Union, Optional
from io import BytesIO
import json
import datetime


class File:
    """
    Representation of a committed file, kept in memory, by reading a `git archive` stream.
    """

    def __init__(self,
             repo: "Giterator",
             buffer: BytesIO,
             tarinfo: tarfile.TarInfo,
     ):
        self.repo = repo
        self._buffer = buffer
        self._tarinfo = tarinfo
        self._data = None

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}', {self.size}, {self.mtime})"

    @property
    def name(self) -> str:
        return self._tarinfo.name

    @property
    def size(self) -> int:
        return self._tarinfo.size

    @property
    def mtime(self) -> int:
        return self._tarinfo.mtime

    @property
    def mtime_dt(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.mtime)

    @property
    def content(self) -> bytes:
        if self._data is None:
            if self._tarinfo.sparse is not None:
                self._data = b""
                for offset, size in self._tarinfo.sparse:
                    self._buffer.seek(offset)
                    self._data += self._buffer.read(size)
            else:
                self._buffer.seek(self._tarinfo.offset_data)
                self._data = self._buffer.read(self._tarinfo.size)

        return self._data

    def text(self, encoding: Optional[str] = None, errors: Optional[str] = None) -> str:
        kwargs = {}
        if encoding:
            kwargs["encoding"] = encoding
        if errors:
            kwargs["errors"] = errors
        return self.content.decode(*kwargs)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "size": self.size,
            "mtime": self.mtime,
            "data": self.content,
        }
