"""ClaimSense — the claims adjudication workflow, automated.

This package does the work an adjuster used to do by hand: read the claim
across the claims, policy and document systems; establish whether cover was in
force; find the clause that governs; weigh the fraud indicators; compute what
is payable; and produce the decision.

It is NOT a claims management system. It owns no system of record and stores
no claims: Northwind's Claims Management System holds those and continues to,
and ClaimSense writes one thing back into it — a recommendation. Delete
ClaimSense and every claim is still there, worked by hand again.

It is also not an assistant that suggests things alongside a human. It performs
the workflow. What remains human is the DECISION: every outcome is produced as a
recommendation carrying the evidence it relied on, and nothing is recorded
against a claim until a licensed adjuster confirms it. That boundary is a
regulatory requirement, not a statement about the automation's confidence.
"""

__version__ = "0.1.0"
