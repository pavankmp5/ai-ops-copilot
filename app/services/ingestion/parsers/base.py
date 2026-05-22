from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.ingestion.models import NormalizedDocument, SourceFile


class DocumentParser(ABC):
    @abstractmethod
    def supports(self, source: SourceFile) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, content: bytes, source: SourceFile) -> NormalizedDocument:
        raise NotImplementedError
