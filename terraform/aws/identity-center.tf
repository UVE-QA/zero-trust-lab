# ---------------------------------------------------------------------------
# Identity Center
#
# NOT BUILT HERE, AND THE REASON IS ARCHITECTURAL RATHER THAN A TODO.
#
# Identity Center lives in the organisation's management account. This stack
# deploys into a workload account, and its credentials cannot administer the
# organisation. Permission sets and assignments therefore belong to a separate
# root with different credentials -- putting them here would produce a plan
# that cannot be applied by the identity it is designed for.
#
# The design intent, recorded so it is not lost:
#
#   - Permission sets are assigned to GROUPS in the internal identity store,
#     never to individual users. When a real identity provider eventually
#     arrives, only the SOURCE of the groups changes; the assignments do not.
#
#   - The tailnet has no identity provider at all (see docs/00-handoff.md 2.1),
#     so this is the one place in the lab where group-based assignment is
#     available. It is worth doing for that contrast alone: the same principle,
#     available on one side of the system and not the other.
#
# When it is built it goes in terraform/identity-center/ with its own provider
# and its own state, not in this directory.
# ---------------------------------------------------------------------------
