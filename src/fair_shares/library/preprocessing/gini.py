"""What happens to a country that has no Gini value.

Analysis-country membership used to require a Gini value, so this case could
not arise: a country without one was dropped from every allocation, including
approaches that never look at inequality. Membership is now decided by
emissions, GDP and population alone, which means a country can reach the
allocation step with no Gini value, and something has to decide what it gets.

``fallback-mean`` gives it the mean of the countries that do have one — the
value Rest-of-World has always received — and records that it was imputed.
``strict`` refuses instead, for work that must not impute silently.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError

#: Policies for analysis countries with no Gini value.
GINI_MISSING_POLICIES = ("fallback-mean", "strict")

#: Used when the caller does not say. Keeps every analysis country a named
#: entity rather than folding it into Rest-of-World.
DEFAULT_GINI_MISSING_POLICY = "fallback-mean"


def gini_missing_policy(config: dict[str, Any]) -> str:
    """Read the missing-Gini policy from a run config.

    Configs written before this setting existed have no key for it, so the
    default applies.
    """
    general = config.get("general") or {}
    return str(general.get("gini_missing_policy") or DEFAULT_GINI_MISSING_POLICY)


def complete_gini(
    gini: pd.DataFrame,
    analysis_countries: set[str],
    *,
    policy: str = DEFAULT_GINI_MISSING_POLICY,
    row_key: str = "ROW",
) -> tuple[pd.DataFrame, set[str]]:
    """Return Gini values for every analysis country, plus Rest-of-World.

    Parameters
    ----------
    gini
        Gini DataFrame indexed by ``['iso3c', 'unit']`` with a ``gini`` column.
    analysis_countries
        Countries in the analysis, decided without reference to Gini.
    policy
        ``fallback-mean`` (default) or ``strict``.
    row_key
        Index key for the Rest-of-World row.

    Returns
    -------
    tuple
        ``(gini_complete, imputed)`` — the Gini table covering every analysis
        country and Rest-of-World, and the set of countries whose value was
        imputed. Rest-of-World is not in ``imputed``: it has always been a mean.

    Raises
    ------
    ConfigurationError
        If ``policy`` is not a known policy.
    DataProcessingError
        If no analysis country has a Gini value, or ``policy`` is ``strict``
        and some analysis country lacks one.
    """
    if policy not in GINI_MISSING_POLICIES:
        raise ConfigurationError(
            f"Unknown Gini missing-value policy {policy!r}. "
            f"Valid options: {', '.join(GINI_MISSING_POLICIES)}."
        )

    observed = gini[
        gini.index.get_level_values("iso3c").isin(analysis_countries)
    ].copy()

    if observed.empty:
        raise DataProcessingError(
            "No Gini coefficient data found for analysis countries. "
            "Cannot calculate ROW average without data."
        )

    missing = sorted(analysis_countries - set(observed.index.get_level_values("iso3c")))

    if missing and policy == "strict":
        raise DataProcessingError(
            f"{len(missing)} analysis countries have no Gini value under the "
            f"'strict' policy: {missing}. Use 'fallback-mean' to impute the "
            "analysis-country mean, or choose a Gini source covering them."
        )

    mean_gini = observed["gini"].mean()

    filler = pd.DataFrame(
        {"gini": [mean_gini] * (len(missing) + 1)},
        index=pd.MultiIndex.from_tuples(
            [(iso3c, "unitless") for iso3c in [*missing, row_key]],
            names=["iso3c", "unit"],
        ),
    )

    return pd.concat([observed, filler]), set(missing)
