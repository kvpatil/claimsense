"""The three client systems, behind one seam.

    CMS  claims management    the claim, the FNOL, the notes, the decision
    PAS  policy administration the policy, coverages, limits, the clause corpus
    DMS  document store        the files and the text OCR pulled out of them

Two backends, one interface:

  * mock  the bundled fixture — zero network, zero keys, zero dollars
  * live  three scoped HTTP contracts, each with its own key

`mock` is not a stub. It is the CI brain and the gate every milestone is
measured on, so it has to answer the same questions with the same shapes the
live path does. Where the two could drift, they do not: both are generated from
platform/db/seed/generate.py in one pass.

THREE clients, not one, even though one Next.js app serves all three namespaces
today. In the engagement these are three vendors with three contracts and three
credentials, and writing them as one client would hide the integration work the
charter is about — and would let a CMS credential read PAS.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent.parent / "data" / "fixture.json"
CORPUS = HERE.parent.parent / "data" / "policy_corpus.json"


REPO_ROOT = HERE.parent.parent.parent


def load_env(path: Path | None = None) -> None:
    """Read .env and keys.env, without a python-dotenv dependency.

    Two files, deliberately. `.env` is wiring — base URLs, the local DSN, model
    ids — and is safe on a screenshare. `keys.env` is credentials and is
    gitignored. Keeping them apart means `cat .env` in a demo cannot leak a
    key, and the one file that must never be committed stays small enough to
    check by eye.

    setdefault, not overwrite: a value already exported wins over either file,
    so CI and the container override without editing anything. Blank values are
    skipped so an unfilled `OPENAI_API_KEY=` in keys.env does not shadow a real
    one from the environment — which would silently force the mock brain.
    """
    files = [path] if path else [REPO_ROOT / ".env", REPO_ROOT / "keys.env"]
    for env in files:
        if not env or not env.exists():
            continue
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if v:
                os.environ.setdefault(k.strip(), v)


class SystemError_(RuntimeError):
    """A client system refused or could not answer. Carries which one."""

    def __init__(self, system: str, message: str):
        self.system = system
        super().__init__(f"[{system}] {message}")


class ClaimsData:
    """One seam over CMS, PAS and DMS."""

    def __init__(self, mock: bool = True):
        self.mock = mock
        self.backend = "fixture" if mock else "live"
        self._fx: dict[str, Any] | None = None
        if mock:
            if not FIXTURE.exists():
                raise FileNotFoundError(
                    f"{FIXTURE} missing — run `make seed` to generate it")
            self._fx = json.loads(FIXTURE.read_text())
        else:
            load_env()
            self._base = {
                "cms": os.environ.get("CMS_BASE_URL", ""),
                "pas": os.environ.get("PAS_BASE_URL", ""),
                "dms": os.environ.get("DMS_BASE_URL", ""),
            }
            self._key = {
                "cms": os.environ.get("CMS_API_KEY", ""),
                "pas": os.environ.get("PAS_API_KEY", ""),
                "dms": os.environ.get("DMS_API_KEY", ""),
            }
            missing = [s for s in ("cms", "pas", "dms")
                       if not self._base[s] or not self._key[s]]
            if missing:
                raise SystemError_(",".join(missing),
                                   "base URL or API key not configured; "
                                   "run `make up` then copy the keys into .env, "
                                   "or pass --mock")

    # -- the reference date the fixture was generated against -----------------
    @property
    def reference_now(self) -> str:
        """When 'now' is, for the clock.

        The fixture pins it so evals cannot start failing on a calendar. The
        live path has no opinion and the caller supplies the real clock.
        """
        return (self._fx or {}).get("_now", "")

    # ---- CMS ---------------------------------------------------------------
    def get_claim(self, claim_id: int | str) -> dict:
        if self.mock:
            c = self._fx["claims"].get(str(claim_id))
            if not c:
                raise SystemError_("cms", f"claim {claim_id} not found")
            return dict(c)
        return self._get("cms", f"/claims/{claim_id}")["claim"]

    def get_fnol(self, claim_id: int | str) -> list[dict]:
        if self.mock:
            return self._fx["fnol_by_claim"].get(str(claim_id), [])
        return self._get("cms", f"/claims/{claim_id}/fnol")["fnol"]

    def get_notes(self, claim_id: int | str) -> list[dict]:
        if self.mock:
            return self._fx["notes_by_claim"].get(str(claim_id), [])
        return self._get("cms", f"/claims/{claim_id}/notes")["notes"]

    def get_fraud_signals(self, claim_id: int | str) -> list[dict]:
        if self.mock:
            return self._fx["signals_by_claim"].get(str(claim_id), [])
        return self._get("cms", f"/claims/{claim_id}/fraud-signals")["signals"]

    def get_adjuster(self, adjuster_id: int | str | None) -> dict | None:
        if adjuster_id is None:
            return None
        if self.mock:
            return self._fx["adjusters"].get(str(adjuster_id))
        return self._get("cms", f"/adjusters/{adjuster_id}").get("adjuster")

    def list_claims(self, limit: int = 100) -> list[dict]:
        if self.mock:
            rows = list(self._fx["claims"].values())
            return sorted(rows, key=lambda c: c["claim_id"])[:limit]
        return self._get("cms", f"/claims?limit={limit}")["claims"]

    # ---- PAS ---------------------------------------------------------------
    def get_policy(self, policy_id: int | str) -> dict | None:
        """None when PAS has no such policy.

        Deliberately NOT an exception. The claim/policy reference crosses a
        vendor boundary with no foreign key behind it, so a dangling id is a
        thing that happens, and the pipeline's job is to report it (ADV-04).
        """
        if self.mock:
            return self._fx["policies"].get(str(policy_id))
        try:
            return self._get("pas", f"/policies/{policy_id}")["policy"]
        except SystemError_ as exc:
            if "404" in str(exc):
                return None
            raise

    def get_coverages(self, policy_id: int | str) -> list[dict]:
        if self.mock:
            return self._fx["coverages_by_policy"].get(str(policy_id), [])
        return self._get("pas", f"/policies/{policy_id}/coverages")["coverages"]

    def get_clauses(self) -> list[dict]:
        """The whole clause corpus. Retrieval ranks locally over this."""
        if self.mock:
            return self._fx["clauses"]
        return self._get("pas", "/clauses")["clauses"]

    # ---- DMS ---------------------------------------------------------------
    def get_documents(self, claim_id: int | str) -> list[dict]:
        """Every document, INCLUDING any flagged poisoned.

        The quarantine happens in the guardrail, not here, and that is on
        purpose: if this method filtered, the quarantine would be invisible and
        unauditable. The pipeline has to SEE the poisoned document in order to
        record that it dropped it.
        """
        if self.mock:
            return self._fx["documents_by_claim"].get(str(claim_id), [])
        return self._get("dms", f"/documents?claim_id={claim_id}")["documents"]

    # ---- the writes --------------------------------------------------------
    def record_decision(self, claim_id: int | str, payload: dict,
                        idem_key: str) -> dict:
        """Write the recommendation to CMS. Idempotent.

        A duplicated claim decision is a duplicated payment, so the key is not
        optional on this path.
        """
        if self.mock:
            return {"decision_id": f"MOCK-{claim_id}", "claim_id": str(claim_id),
                    "mock": True, **payload}
        return self._post("cms", f"/claims/{claim_id}/decisions", payload, idem_key)

    def request_document(self, claim_id: int | str, doc_type: str, reason: str,
                         idem_key: str) -> dict:
        """The MORE_INFO write: ask for a named document. Idempotent — asking
        twice because a pipeline retried must not send two letters."""
        if self.mock:
            return {"request_id": f"MOCK-REQ-{claim_id}-{doc_type}", "mock": True}
        return self._post("dms", "/document-requests",
                          {"claim_id": claim_id, "doc_type": doc_type,
                           "reason": reason}, idem_key)

    # ---- HTTP --------------------------------------------------------------
    def _get(self, system: str, path: str) -> dict:
        import requests
        r = requests.get(f"{self._base[system]}{path}",
                         headers={"Authorization": f"Bearer {self._key[system]}"},
                         timeout=30)
        if r.status_code >= 400:
            raise SystemError_(system, f"{r.status_code} GET {path}: {r.text[:200]}")
        return r.json()

    def _post(self, system: str, path: str, body: dict, idem_key: str) -> dict:
        import requests
        r = requests.post(f"{self._base[system]}{path}",
                          headers={"Authorization": f"Bearer {self._key[system]}",
                                   "Content-Type": "application/json",
                                   "Idempotency-Key": idem_key},
                          json=body, timeout=30)
        if r.status_code >= 400:
            raise SystemError_(system, f"{r.status_code} POST {path}: {r.text[:200]}")
        return r.json()


def claim_bundle(data: ClaimsData, claim_id: int | str) -> dict:
    """Everything one claim needs, gathered across all three systems.

    This is the function that makes the engagement's point concrete: the
    adjuster's manual work is three systems and a lot of tab-switching, and
    this is that work, once, in code.
    """
    claim = data.get_claim(claim_id)
    policy = data.get_policy(claim["policy_id"])
    return {
        "claim": claim,
        "fnol": data.get_fnol(claim_id),
        "notes": data.get_notes(claim_id),
        "signals": data.get_fraud_signals(claim_id),
        "policy": policy,
        "coverages": data.get_coverages(claim["policy_id"]) if policy else [],
        "documents": data.get_documents(claim_id),
        "adjuster": data.get_adjuster(claim.get("assigned_adjuster_id")),
    }
