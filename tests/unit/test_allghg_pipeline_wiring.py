"""Integration tests for composite-category pipeline wiring.

Verifies:
- emission_category="all-ghg" drives target-aware decomposition behavior
- build_source_id() always includes emission_category in the source_id
- get_final_categories() is target-aware (AR6 single-pass, RCBs decompose)
- get_compatible_approaches() returns pathway approaches for composite runs
- validate_data_source_config() returns target_type="composite" for composite runs
- get_allocation_output_dir() returns co2/ and non-co2/ subdirectories for composite
- run_composite_preprocessing() guards on composite categories, not target name
- run_composite_preprocessing() dispatches target-appropriate preprocessing
- validate_target_source_compatibility() handles all targets correctly
- is_composite_category() and needs_decomposition() predicates
"""

from __future__ import annotations

import pytest

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.pipeline.preprocessing import get_allocation_output_dir
from fair_shares.library.utils.data.config import (
    ALL_GHG_CO2_CATEGORIES,
    COMPOSITE_CATEGORIES,
    build_source_id,
    get_compatible_approaches,
    get_final_categories,
    is_composite_category,
    needs_decomposition,
)

# ---------------------------------------------------------------------------
# ALL_GHG_CO2_CATEGORIES constant
# ---------------------------------------------------------------------------


class TestAllGhgCo2Categories:
    """ALL_GHG_CO2_CATEGORIES distinguishes CO2 from non-CO2 categories."""

    def test_contains_co2_ffi_and_co2(self):
        assert ALL_GHG_CO2_CATEGORIES == ("co2-ffi", "co2")

    def test_does_not_contain_nonco2(self):
        assert "all-ghg-ex-co2-lulucf" not in ALL_GHG_CO2_CATEGORIES

    def test_co2_categories_not_in_composite(self):
        """co2-ffi and co2 are NOT composite categories."""
        assert "co2-ffi" not in COMPOSITE_CATEGORIES
        assert "co2" not in COMPOSITE_CATEGORIES


# ---------------------------------------------------------------------------
# is_composite_category predicate
# ---------------------------------------------------------------------------


class TestIsCompositeCategory:
    """is_composite_category() correctly identifies composite categories."""

    def test_allghg_is_composite(self):
        assert is_composite_category("all-ghg") is True

    def test_allghg_ex_co2_lulucf_is_composite(self):
        assert is_composite_category("all-ghg-ex-co2-lulucf") is True

    def test_co2_ffi_is_not_composite(self):
        assert is_composite_category("co2-ffi") is False

    def test_co2_is_not_composite(self):
        assert is_composite_category("co2") is False


class TestNeedsDecomposition:
    """needs_decomposition() is True only for non-AR6 + composite combos."""

    def test_rcbs_allghg_needs_decomposition(self):
        assert needs_decomposition("rcbs", "all-ghg") is True

    def test_rcbs_allghg_ex_co2_needs_decomposition(self):
        assert needs_decomposition("rcbs", "all-ghg-ex-co2-lulucf") is True

    def test_rcb_pathways_allghg_needs_decomposition(self):
        assert needs_decomposition("rcb-pathways", "all-ghg") is True

    def test_ar6_allghg_does_not_need_decomposition(self):
        assert needs_decomposition("pathway", "all-ghg") is False

    def test_ar6_allghg_ex_co2_does_not_need_decomposition(self):
        assert needs_decomposition("pathway", "all-ghg-ex-co2-lulucf") is False

    def test_rcbs_co2ffi_does_not_need_decomposition(self):
        assert needs_decomposition("rcbs", "co2-ffi") is False

    def test_ar6_co2ffi_does_not_need_decomposition(self):
        assert needs_decomposition("pathway", "co2-ffi") is False


# ---------------------------------------------------------------------------
# build_source_id
# ---------------------------------------------------------------------------


class TestBuildSourceIdAllghg:
    """build_source_id() generates correct IDs with emission_category always included."""

    _BASE = dict(
        emissions="primap-202503",
        gdp="wdi-2025",
        population="un-owid-2025",
        gini="unu-wider-2025",
    )

    def test_rcbs_allghg_source_id(self):
        """rcbs + all-ghg includes 'all-ghg' in source_id."""
        sid = build_source_id(**self._BASE, target="rcbs", emission_category="all-ghg")
        assert sid == "primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcbs_all-ghg"

    def test_ar6_allghg_source_id(self):
        """pathway + all-ghg includes 'all-ghg' in source_id."""
        sid = build_source_id(
            **self._BASE, target="pathway", emission_category="all-ghg"
        )
        assert sid.endswith("_pathway_all-ghg")

    def test_rcbs_co2ffi_source_id(self):
        """rcbs + co2-ffi includes 'co2-ffi' in source_id."""
        sid = build_source_id(**self._BASE, target="rcbs", emission_category="co2-ffi")
        assert sid.endswith("_rcbs_co2-ffi")

    def test_ar6_co2ffi_source_id(self):
        """pathway + co2-ffi includes 'co2-ffi' — unchanged from before."""
        sid = build_source_id(
            **self._BASE, target="pathway", emission_category="co2-ffi"
        )
        assert sid.endswith("_pathway_co2-ffi")

    def test_emission_category_always_present(self):
        """emission_category is always the last part of source_id."""
        for target in ("pathway", "rcbs", "rcb-pathways"):
            for cat in ("co2-ffi", "all-ghg"):
                sid = build_source_id(
                    **self._BASE, target=target, emission_category=cat
                )
                assert sid.endswith(f"_{cat}")

    def test_different_categories_produce_different_ids(self):
        """Different emission_categories on the same target produce different source_ids."""
        sid_co2 = build_source_id(
            **self._BASE, target="rcbs", emission_category="co2-ffi"
        )
        sid_allghg = build_source_id(
            **self._BASE, target="rcbs", emission_category="all-ghg"
        )
        assert sid_co2 != sid_allghg

    def test_rcb_pathways_includes_generator(self):
        """rcb-pathways still includes generator suffix."""
        sid = build_source_id(
            **self._BASE,
            target="rcb-pathways",
            emission_category="co2-ffi",
            rcb_generator="exponential-decay",
        )
        assert "rcb-pathways-exponential-decay" in sid
        assert sid.endswith("_co2-ffi")


# ---------------------------------------------------------------------------
# get_final_categories — now target-aware
# ---------------------------------------------------------------------------


class TestGetFinalCategories:
    """get_final_categories() returns correct categories per target + emission_category."""

    def test_ar6_allghg_returns_single_category(self):
        """pathway target has direct data for all-ghg — single pass, no decomposition."""
        cats = get_final_categories("pathway", "all-ghg")
        assert cats == ("all-ghg",)

    def test_rcbs_allghg_returns_co2_and_nonco2(self):
        """RCBs + all-ghg decomposes into CO2 + non-CO2."""
        cats = get_final_categories("rcbs", "all-ghg")
        assert cats == ("co2", "non-co2")

    def test_rcb_pathways_allghg_returns_co2_and_nonco2(self):
        """rcb-pathways + all-ghg decomposes into CO2 + non-CO2."""
        cats = get_final_categories("rcb-pathways", "all-ghg")
        assert cats == ("co2", "non-co2")

    def test_ar6_allghg_ex_co2_returns_single_category(self):
        """pathway target + all-ghg-ex-co2-lulucf: single pass."""
        cats = get_final_categories("pathway", "all-ghg-ex-co2-lulucf")
        assert cats == ("all-ghg-ex-co2-lulucf",)

    def test_rcbs_allghg_ex_co2_returns_co2ffi_and_nonco2(self):
        """RCBs + all-ghg-ex-co2-lulucf decomposes into co2-ffi + non-co2."""
        cats = get_final_categories("rcbs", "all-ghg-ex-co2-lulucf")
        assert cats == ("co2-ffi", "non-co2")

    def test_co2ffi_returns_single_category_for_any_target(self):
        """Pure CO2-FFI is always a single pass."""
        for target in ("pathway", "rcbs", "rcb-pathways"):
            cats = get_final_categories(target, "co2-ffi")
            assert cats == ("co2-ffi",)


# ---------------------------------------------------------------------------
# get_compatible_approaches
# ---------------------------------------------------------------------------


class TestGetCompatibleApproachesAllghg:
    """get_compatible_approaches() returns correct approaches for all-GHG runs."""

    def test_rcbs_allghg_returns_both_approaches(self):
        """rcbs + all-ghg returns both budget and pathway approaches."""
        approaches = get_compatible_approaches("rcbs", emission_category="all-ghg")
        budget_in = any(a.endswith("-budget") for a in approaches)
        pathway_in = any(not a.endswith("-budget") for a in approaches)
        assert budget_in and pathway_in

    def test_ar6_allghg_returns_pathway_approaches(self):
        approaches = get_compatible_approaches("pathway", emission_category="all-ghg")
        assert not any(a.endswith("-budget") for a in approaches)

    def test_rcbs_co2ffi_returns_budget_approaches(self):
        """rcbs + co2-ffi still returns budget approaches."""
        approaches = get_compatible_approaches("rcbs", emission_category="co2-ffi")
        assert all(a.endswith("-budget") for a in approaches)

    def test_ar6_co2ffi_returns_pathway_approaches(self):
        approaches = get_compatible_approaches("pathway", emission_category="co2-ffi")
        assert not any(a.endswith("-budget") for a in approaches)

    def test_allghg_includes_per_capita(self):
        approaches = get_compatible_approaches("rcbs", emission_category="all-ghg")
        assert "equal-per-capita" in approaches
        assert "per-capita-adjusted" in approaches


# ---------------------------------------------------------------------------
# validate_data_source_config (target_type only — no real data files needed)
# ---------------------------------------------------------------------------


class TestValidateDataSourceConfigAllghg:
    """validate_data_source_config() correctly classifies target types."""

    _SOURCES = {
        "emissions": "primap-202503",
        "gdp": "wdi-2025",
        "population": "un-owid-2025",
        "gini": "unu-wider-2025",
    }

    def test_rcbs_allghg_target_type(self):
        from fair_shares.library.utils.data.config import validate_data_source_config

        result = validate_data_source_config(
            emission_category="all-ghg",
            active_sources={**self._SOURCES, "target": "rcbs"},
            verbose=False,
        )
        assert result["target_type"] == "composite"

    def test_ar6_allghg_target_type(self):
        from fair_shares.library.utils.data.config import validate_data_source_config

        result = validate_data_source_config(
            emission_category="all-ghg",
            active_sources={**self._SOURCES, "target": "pathway"},
            verbose=False,
        )
        assert result["target_type"] == "composite"

    def test_ar6_co2ffi_target_type(self):
        from fair_shares.library.utils.data.config import validate_data_source_config

        result = validate_data_source_config(
            emission_category="co2-ffi",
            active_sources={**self._SOURCES, "target": "pathway"},
            verbose=False,
        )
        assert result["target_type"] == "pathway"

    def test_rcbs_co2ffi_target_type(self):
        from fair_shares.library.utils.data.config import validate_data_source_config

        result = validate_data_source_config(
            emission_category="co2-ffi",
            active_sources={**self._SOURCES, "target": "rcbs"},
            verbose=False,
        )
        assert result["target_type"] == "budget"

    def test_unknown_target_reports_unknown(self):
        from fair_shares.library.utils.data.config import validate_data_source_config

        result = validate_data_source_config(
            emission_category="co2-ffi",
            active_sources={**self._SOURCES, "target": "nonexistent-target"},
            verbose=False,
        )
        assert result["target_type"] == "unknown"
        assert not result["valid"]

    def test_compound_targets_are_rejected(self):
        """Old compound target names (rcb-allghg, rcb-pathways-allghg) are no longer valid."""
        from fair_shares.library.utils.data.config import validate_data_source_config

        for old_target in ("rcb-allghg", "rcb-pathways-allghg"):
            result = validate_data_source_config(
                emission_category="co2-ffi",
                active_sources={**self._SOURCES, "target": old_target},
                verbose=False,
            )
            assert result["target_type"] == "unknown"
            assert not result["valid"]


# ---------------------------------------------------------------------------
# get_allocation_output_dir
# ---------------------------------------------------------------------------


class TestGetAllocationOutputDir:
    """get_allocation_output_dir() returns correct subdirectory paths."""

    def test_allghg_co2_subdir(self, tmp_path):
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "rcbs", "co2", emission_category="all-ghg"
        )
        assert out == base / "co2"
        assert out.exists()

    def test_allghg_nonco2_subdir(self, tmp_path):
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "rcbs", "non-co2", emission_category="all-ghg"
        )
        assert out == base / "non-co2"
        assert out.exists()

    def test_ar6_allghg_co2_subdir(self, tmp_path):
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "pathway", "co2", emission_category="all-ghg"
        )
        assert out == base / "co2"

    def test_ar6_co2ffi_no_subdir_split(self, tmp_path):
        """Non-composite: pathway target returns base dir unchanged."""
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "pathway", "co2", emission_category="co2-ffi"
        )
        assert out == base

    def test_rcbs_co2ffi_no_subdir_split(self, tmp_path):
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "rcbs", "co2", emission_category="co2-ffi"
        )
        assert out == base

    def test_allghg_ex_co2_lulucf_co2_subdir(self, tmp_path):
        """all-ghg-ex-co2-lulucf is now composite, so it also creates subdirs."""
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "rcbs", "co2", emission_category="all-ghg-ex-co2-lulucf"
        )
        assert out == base / "co2"
        assert out.exists()

    def test_allghg_ex_co2_lulucf_nonco2_subdir(self, tmp_path):
        """all-ghg-ex-co2-lulucf creates non-co2 subdirectory too."""
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        out = get_allocation_output_dir(
            base, "rcbs", "non-co2", emission_category="all-ghg-ex-co2-lulucf"
        )
        assert out == base / "non-co2"
        assert out.exists()

    def test_invalid_gas_raises_value_error(self, tmp_path):
        base = tmp_path / "allocations" / "folder"
        base.mkdir(parents=True)
        with pytest.raises(ValueError, match="gas must be"):
            get_allocation_output_dir(
                base, "rcbs", "all-ghg", emission_category="all-ghg"
            )

    def test_creates_directory_if_missing(self, tmp_path):
        base = tmp_path / "does_not_exist_yet"
        out = get_allocation_output_dir(
            base, "rcbs", "co2", emission_category="all-ghg"
        )
        assert out.exists()


# ---------------------------------------------------------------------------
# run_composite_preprocessing — guard on composite categories
# ---------------------------------------------------------------------------


class TestRunAllghgPreprocessingGuard:
    """run_composite_preprocessing() raises for non-composite emission_category."""

    def test_raises_for_co2ffi(self):
        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with pytest.raises(ConfigurationError):
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "pathway"},
                emission_category="co2-ffi",
            )

    def test_raises_for_co2(self):
        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with pytest.raises(ConfigurationError):
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "rcbs"},
                emission_category="co2",
            )

    def test_accepts_allghg(self):
        """all-ghg is accepted (guard does not raise)."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with patch(
            "fair_shares.library.pipeline.preprocessing.run_pathway_preprocessing"
        ):
            # Should not raise ConfigurationError
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "pathway"},
                emission_category="all-ghg",
            )

    def test_accepts_allghg_ex_co2_lulucf(self):
        """all-ghg-ex-co2-lulucf is now accepted (it's a composite category)."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with patch(
            "fair_shares.library.pipeline.preprocessing.run_pathway_preprocessing"
        ):
            # Should not raise ConfigurationError
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "pathway"},
                emission_category="all-ghg-ex-co2-lulucf",
            )


# ---------------------------------------------------------------------------
# validate_target_source_compatibility
# ---------------------------------------------------------------------------


class TestTargetSourceCompatibilityAllghg:
    """validate_target_source_compatibility handles all targets correctly."""

    def test_ar6_rejects_budget_approaches(self):
        from fair_shares.library.exceptions import AllocationError
        from fair_shares.library.validation.config import (
            validate_target_source_compatibility,
        )

        config = {
            "equal-per-capita-budget": [{"allocation-year": 2020}],
        }
        with pytest.raises(AllocationError, match="Budget allocation approaches"):
            validate_target_source_compatibility(config, "pathway")

    def test_ar6_accepts_pathway_approaches(self):
        from fair_shares.library.validation.config import (
            validate_target_source_compatibility,
        )

        config = {
            "equal-per-capita": [{"first-allocation-year": 2020}],
            "per-capita-adjusted": [{"first-allocation-year": 2020}],
        }
        # Should not raise
        validate_target_source_compatibility(config, "pathway")

    def test_rcb_pathways_rejects_budget_approaches(self):
        from fair_shares.library.exceptions import AllocationError
        from fair_shares.library.validation.config import (
            validate_target_source_compatibility,
        )

        config = {
            "per-capita-adjusted-budget": [{"allocation-year": 2020}],
        }
        with pytest.raises(AllocationError, match="Budget allocation approaches"):
            validate_target_source_compatibility(config, "rcb-pathways")

    def test_rcb_pathways_accepts_pathway_approaches(self):
        from fair_shares.library.validation.config import (
            validate_target_source_compatibility,
        )

        config = {
            "cumulative-per-capita-convergence": [{"first-allocation-year": 2020}],
        }
        validate_target_source_compatibility(config, "rcb-pathways")


# ---------------------------------------------------------------------------
# run_composite_preprocessing — target-aware dispatch
# ---------------------------------------------------------------------------


class TestRunAllghgPreprocessingDispatch:
    """run_composite_preprocessing() dispatches correct preprocessing per target."""

    def test_ar6_allghg_calls_pathway_once(self):
        """pathway + all-ghg: single pathway call (pathway target has direct all-ghg data)."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with patch(
            "fair_shares.library.pipeline.preprocessing.run_pathway_preprocessing"
        ) as mock_pp:
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "pathway"},
                emission_category="all-ghg",
            )

        assert mock_pp.call_count == 1
        assert mock_pp.call_args.args[3] == "all-ghg"

    def test_rcbs_allghg_uses_rcb_for_co2_and_nonco2_preprocessing(self):
        """rcbs + all-ghg: 1 RCB call for CO2 + 1 non-co2 preprocessing call."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with (
            patch(
                "fair_shares.library.pipeline.preprocessing.run_rcb_preprocessing"
            ) as mock_rcb,
            patch(
                "fair_shares.library.pipeline.preprocessing.run_non_co2_preprocessing"
            ) as mock_nonco2,
        ):
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "rcbs"},
                emission_category="all-ghg",
            )

        # CO2 pass: single RCB preprocessing call for "co2"
        assert mock_rcb.call_count == 1
        assert mock_rcb.call_args.args[3] == "co2"

        # Non-CO2 pass: non-co2 preprocessing
        assert mock_nonco2.call_count == 1

    def test_rcb_pathways_allghg_uses_pathway_for_co2_and_nonco2_preprocessing(self):
        """rcb-pathways + all-ghg: 1 pathway call for CO2 + 1 non-co2 preprocessing call."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        with (
            patch(
                "fair_shares.library.pipeline.preprocessing.run_pathway_preprocessing"
            ) as mock_pp,
            patch(
                "fair_shares.library.pipeline.preprocessing.run_non_co2_preprocessing"
            ) as mock_nonco2,
        ):
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "rcb-pathways"},
                emission_category="all-ghg",
            )

        # CO2 pass: single pathway preprocessing call for "co2"
        assert mock_pp.call_count == 1
        assert mock_pp.call_args.args[3] == "co2"

        # Non-CO2 pass: non-co2 preprocessing
        assert mock_nonco2.call_count == 1

    def test_rcbs_allghg_pass_order_is_co2_then_nonco2(self):
        """CO2 pass runs before non-CO2 pass."""
        from unittest.mock import patch

        from fair_shares.library.pipeline.preprocessing import (
            run_composite_preprocessing,
        )

        call_order = []

        def track_rcb(*args, **kwargs):
            call_order.append(("rcb", args[3]))

        def track_nonco2(*args, **kwargs):
            call_order.append(("non-co2",))

        with (
            patch(
                "fair_shares.library.pipeline.preprocessing.run_rcb_preprocessing",
                side_effect=track_rcb,
            ),
            patch(
                "fair_shares.library.pipeline.preprocessing.run_non_co2_preprocessing",
                side_effect=track_nonco2,
            ),
        ):
            run_composite_preprocessing(
                config={},
                source_id="test",
                active_sources={"target": "rcbs"},
                emission_category="all-ghg",
            )

        assert call_order[0] == ("rcb", "co2")
        assert call_order[1] == ("non-co2",)
