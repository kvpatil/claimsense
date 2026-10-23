"""BM25 over the clause corpus. Lexical, local, deterministic, $0.

WHY NOT EMBEDDINGS. Three reasons, in order of weight:

  1. The gate has to run with no key and no network. An embedding retriever
     needs a model call or a vector store, and --mock is what CI measures.
  2. Determinism. The same claim must retrieve the same clauses on every run,
     or an eval that passes today fails tomorrow for reasons nobody changed.
  3. The query is not conversational. It is a peril plus a handful of policy
     terms against ~46 clauses of controlled legal vocabulary — the setting
     where lexical matching is strongest and semantic search buys least.

This is a real trade-off, not a free win: BM25 will miss a clause that says
"earth movement" when the claim says "the ground shifted". The deterministic
peril pre-filter below is what covers that gap, because `perils` is structured
data on the clause rather than something the ranker has to infer.

Implemented from the standard BM25 Okapi formula rather than pulled from a
library, because it is twenty lines and a dependency here would have to be
installed before the $0 gate could run.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

K1 = 1.5    # term-frequency saturation
B = 0.75    # length normalisation

# Policy prose is dense with words that carry no discriminating signal here —
# every clause says "we", "loss", "policy", "insured". Left in, they flatten the
# ranking; a clause is retrieved for being long rather than for being relevant.
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "by", "is",
    "are", "be", "been", "was", "were", "this", "that", "these", "those", "it",
    "its", "as", "at", "from", "with", "any", "all", "not", "we", "you", "your",
    "our", "us", "will", "shall", "may", "which", "who", "if", "under", "over",
    "than", "then", "there", "their", "has", "have", "had", "do", "does", "no",
}

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in STOP and len(t) > 2]


@dataclass
class Hit:
    clause_id: str
    score: float
    clause: dict

    @property
    def title(self) -> str:
        return self.clause["title"]


class Retriever:
    """A BM25 index over the clause corpus, built once per run."""

    def __init__(self, clauses: list[dict]):
        self.clauses = clauses
        self._docs: dict[str, list[str]] = {}
        for c in clauses:
            # Title and section are indexed alongside the body because a clause
            # named "Water Damage" should answer a water query even when the
            # body spends its words on the carve-outs.
            #
            # `keywords` carries the vocabulary CLAIMANTS use. Without it the
            # wear-and-tear exclusion scored DEAD LAST on a claim that said
            # "the roof has been leaking for a while and the ceiling is sagging"
            # — measured — because the clause says "deterioration" and "rot"
            # and the narrative says neither. That is the classic BM25
            # vocabulary mismatch, and it is not fixable by retrieving more:
            # the right clause was 25th of 25.
            self._docs[c["clause_id"]] = tokenize(
                f"{c['title']} {c['section']} {c['body']} {c.get('keywords', '')}")

        self._len = {cid: len(toks) for cid, toks in self._docs.items()}
        self._avg = (sum(self._len.values()) / len(self._len)) if self._len else 0.0
        self._tf = {cid: Counter(toks) for cid, toks in self._docs.items()}

        df: Counter[str] = Counter()
        for toks in self._docs.values():
            df.update(set(toks))
        n = len(self._docs)
        # Standard BM25 IDF with the +0.5 smoothing, floored at a small positive
        # value: a term in every document would otherwise score negative and
        # actively push relevant clauses DOWN the ranking.
        self._idf = {
            t: max(1e-6, math.log(1 + (n - c + 0.5) / (c + 0.5)))
            for t, c in df.items()
        }

    def search(self, query: str, *, product: str | None = None,
               peril: str | None = None, top_k: int = 8) -> list[Hit]:
        """Rank clauses for a query, pre-filtered deterministically.

        The pre-filter is doing real work and is NOT an optimisation: an AUTO
        racing exclusion must never be retrieved for a homeowners water claim,
        and no amount of lexical scoring guarantees that. Product and peril are
        structured fields, so the filter is exact where the ranker is fuzzy.
        """
        candidates = self._prefilter(product, peril)
        q = tokenize(query)
        if not q:
            return []

        scored: list[Hit] = []
        for c in candidates:
            cid = c["clause_id"]
            tf, dl = self._tf[cid], self._len[cid]
            s = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + K1 * (1 - B + B * dl / self._avg) if self._avg else 1.0
                s += self._idf.get(term, 0.0) * (f * (K1 + 1)) / denom
            if s > 0:
                scored.append(Hit(clause_id=cid, score=round(s, 4), clause=c))

        scored.sort(key=lambda h: (-h.score, h.clause_id))
        return scored[:top_k]

    def _prefilter(self, product: str | None, peril: str | None) -> list[dict]:
        out = []
        for c in self.clauses:
            # 'ALL' clauses are the general provisions and apply to every
            # product; they are where lapse and policy-period live, which are
            # the clauses the hardest cases turn on.
            if product and c["product"] not in (product, "ALL"):
                continue
            # An empty `perils` means the clause is peril-agnostic (conditions,
            # definitions, general provisions) and must stay in the candidate
            # set — filtering those out would lose the deductible clause on
            # every claim.
            if peril and c["perils"] and peril not in c["perils"]:
                continue
            out.append(c)
        return out

    def by_id(self, clause_id: str) -> dict | None:
        for c in self.clauses:
            if c["clause_id"] == clause_id:
                return c
        return None


def retrieve(clauses: list[dict], query: str, **kw) -> list[Hit]:
    return Retriever(clauses).search(query, **kw)
