"""Tests focused on whether the assistant remembers user data."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory.long_term import init_db, add_memory
from memory.retrieval import retrieve
from memory.extractor import extract_local
import memory.retrieval as retrieval_module


def _fake_encode(text: str) -> list[float]:
    t = text.lower()
    if "peanut" in t:
        return [1.0, 0.0]
    if "tokyo" in t:
        return [0.0, 1.0]
    if "paris" in t:
        return [0.8, 0.2]
    return [0.5, 0.5]


class TestMemoryRemember(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(tempfile.gettempdir()) / "test_memory_remember.db"
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)

        # Monkeypatch retrieval to avoid heavy embedding model
        self._orig_encode = retrieval_module.encode
        self._orig_refine = retrieval_module.jepa_inspired_refine
        retrieval_module.encode = _fake_encode
        retrieval_module.jepa_inspired_refine = lambda q, mems, alpha=0.1: q

    def tearDown(self):
        retrieval_module.encode = self._orig_encode
        retrieval_module.jepa_inspired_refine = self._orig_refine
        if self.db_path.exists():
            self.db_path.unlink()

    def test_remembers_allergy_fact(self):
        add_memory("allergic to peanuts", "personal", _fake_encode("allergic to peanuts"), self.db_path)
        add_memory("going to Tokyo", "travel", _fake_encode("going to Tokyo"), self.db_path)

        mems = retrieve("am i allergic to peanuts", top_k=1, db_path=self.db_path, use_jepa_refine=False)
        self.assertTrue(mems)
        self.assertIn("peanuts", mems[0].content.lower())

    def test_remembers_location_fact_from_extractor(self):
        facts = extract_local("I live in Paris and I love croissants.")
        for f in facts:
            add_memory(f["content"], f["category"], _fake_encode(f["content"]), self.db_path)

        mems = retrieve("where do i live?", top_k=3, db_path=self.db_path, use_jepa_refine=False)
        self.assertTrue(any("paris" in m.content.lower() for m in mems))

    def test_returns_memory_without_embeddings(self):
        add_memory("likes jazz music", "misc", None, self.db_path)
        mems = retrieve("what music do i like?", top_k=2, db_path=self.db_path, use_jepa_refine=False)
        self.assertTrue(any("jazz" in m.content.lower() for m in mems))


if __name__ == "__main__":
    unittest.main()
