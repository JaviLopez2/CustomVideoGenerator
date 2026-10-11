"""Experimental state applicability schema; published observer stays unchanged.

This constrains only state applicability. Relational structure/presence rules
and admission policy still require the published observer's runtime validation.
"""
from scripts import scoped_structure_observations as published

VERSION = "scope-compatible-state-schema-1"


def schema(scope):
    declared = published.validate_scope(scope)
    result = published.schema()
    result["properties"]["allowed_state_change"]["enum"] = (
        ["observed", "not_observed", "uncertain"] if declared["allowed_state_changes"] else ["not_applicable"]
    )
    return result


def payload(reference, candidate, scope):
    result = published.payload(reference, candidate, scope)
    result["response_format"]["json_schema"]["schema"] = schema(scope)
    return result
