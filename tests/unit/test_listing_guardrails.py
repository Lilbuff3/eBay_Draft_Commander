"""
Tests for the listing-quality guardrails layer.

Four checks sit between AI/pricing output and eBay submission:
- duplicate detection (perceptual photo-hash, dHash)
- title hygiene (strip dangling fragments, dedupe repeated words)
- brand/aspect normalization (blocklist -> "Unbranded", "A / B" -> "A")
- price sanity (no-comp outlier, or > 3x comp median)

See docs/superpowers/specs/2026-06-27-listing-quality-guardrails-design.md.
"""
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.app.services.listing_guardrails import (
    apply_pre_listing_guardrails,
    check_price_sanity,
    clean_title,
    compute_photo_hashes,
    find_duplicate,
    _required_matches,
    normalize_aspects,
)
from backend.app.core.constants import DUP_HASH_DISTANCE


# ---------------------------------------------------------------------------
# clean_title
# ---------------------------------------------------------------------------

class TestCleanTitle:
    def test_strips_dangling_trailing_open_paren_and_comma(self):
        assert clean_title("Duracell AA Batteries (Alkaline,") == "Duracell AA Batteries"

    def test_strips_dangling_trailing_comma(self):
        assert clean_title("Vintage Brass Lamp, Working,") == "Vintage Brass Lamp, Working"

    def test_strips_dangling_trailing_colon_and_dash(self):
        assert clean_title("Sencore LC102 Meter -") == "Sencore LC102 Meter"
        assert clean_title("Sencore LC102 Meter:") == "Sencore LC102 Meter"

    def test_collapses_consecutive_duplicate_words_case_insensitive(self):
        assert clean_title("Sencore Sencore LC102 Capacitor Tester") == "Sencore LC102 Capacitor Tester"
        assert clean_title("Cassette cassette Player Vintage") == "Cassette Player Vintage"

    def test_normalizes_whitespace(self):
        assert clean_title("Vintage   Brass   Lamp") == "Vintage Brass Lamp"

    def test_clean_title_already_clean_is_noop(self):
        title = "Aiwa CSD-ES227 Stereo Boombox Cassette Player"
        assert clean_title(title) == title

    def test_never_exceeds_80_chars_no_mid_word_cut(self):
        long_title = "A " * 60 + "Widget"
        cleaned = clean_title(long_title)
        assert len(cleaned) <= 80
        assert not cleaned.endswith(" A")
        # No truncation should leave a half-word fragment.
        assert all(w for w in cleaned.split(" "))

    def test_empty_title_returns_empty(self):
        assert clean_title("") == ""

    def test_none_title_returns_empty(self):
        assert clean_title(None) == ""


# ---------------------------------------------------------------------------
# normalize_aspects
# ---------------------------------------------------------------------------

class TestNormalizeAspects:
    def test_blocklisted_brand_mapped_to_unbranded(self):
        specs = {"Brand": "Signed"}
        assert normalize_aspects(specs)["Brand"] == "Unbranded"

    def test_blocklisted_brand_case_insensitive(self):
        specs = {"Brand": "signed"}
        assert normalize_aspects(specs)["Brand"] == "Unbranded"

    def test_slash_separated_brand_takes_first(self):
        specs = {"Brand": "Disney / Chronicle Books"}
        assert normalize_aspects(specs)["Brand"] == "Disney"

    def test_valid_brand_left_untouched(self):
        specs = {"Brand": "Sencore"}
        assert normalize_aspects(specs)["Brand"] == "Sencore"

    def test_empty_brand_dropped(self):
        specs = {"Brand": "", "Color": "Red"}
        result = normalize_aspects(specs)
        assert "Brand" not in result
        assert result["Color"] == "Red"

    def test_no_brand_key_is_noop(self):
        specs = {"Color": "Red", "Size": "Large"}
        assert normalize_aspects(specs) == specs

    def test_other_aspects_untouched(self):
        specs = {"Brand": "Various", "Material": "Wood"}
        result = normalize_aspects(specs)
        assert result["Material"] == "Wood"
        assert result["Brand"] == "Unbranded"


# ---------------------------------------------------------------------------
# compute_photo_hashes / find_duplicate
# ---------------------------------------------------------------------------

def _make_image(path, fill, size=(64, 64)):
    img = Image.new("RGB", size, color=fill)
    img.save(path)
    return str(path)


class TestComputePhotoHashes:
    def test_identical_images_hash_to_zero_distance(self, tmp_path):
        p1 = _make_image(tmp_path / "a.jpg", (10, 20, 30))
        p2 = _make_image(tmp_path / "b.jpg", (10, 20, 30))
        hashes1 = compute_photo_hashes([p1])
        hashes2 = compute_photo_hashes([p2])
        assert hashes1 == hashes2
        assert len(hashes1) == 1
        # 64-bit hash -> 16 hex chars
        assert len(hashes1[0]) == 16

    def test_different_images_hash_differently(self, tmp_path):
        # A checkerboard vs. a solid fill should differ enough to land outside
        # the duplicate-distance threshold (dHash compares adjacent-column
        # brightness, so alternating bright/dark columns flips many bits
        # relative to a flat fill).
        checker = Image.new("RGB", (64, 64))
        for x in range(64):
            for y in range(64):
                shade = 240 if (x // 8 + y // 8) % 2 == 0 else 10
                checker.putpixel((x, y), (shade, shade, shade))
        p1 = tmp_path / "checker.jpg"
        checker.save(p1)
        p2 = _make_image(tmp_path / "solid.jpg", (200, 200, 200))

        h1 = compute_photo_hashes([str(p1)])[0]
        h2 = compute_photo_hashes([str(p2)])[0]
        distance = bin(int(h1, 16) ^ int(h2, 16)).count("1")
        assert distance > DUP_HASH_DISTANCE

    def test_skips_unreadable_image_without_crashing(self, tmp_path):
        bad = tmp_path / "not_an_image.jpg"
        bad.write_bytes(b"this is not a valid jpeg")
        good = _make_image(tmp_path / "good.jpg", (5, 5, 5))
        hashes = compute_photo_hashes([str(bad), good])
        assert len(hashes) == 1

    def test_empty_list_returns_empty(self):
        assert compute_photo_hashes([]) == []

    def test_missing_path_skipped(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.jpg")
        assert compute_photo_hashes([missing]) == []


class TestFindDuplicate:
    def test_identical_hash_within_distance_flags_match(self):
        recent_jobs = [{"id": "job1", "listing_id": "L1", "photo_hashes": ["abcd1234abcd1234"]}]
        result = find_duplicate(["abcd1234abcd1234"], recent_jobs, max_distance=6)
        assert result == {"id": "job1", "listing_id": "L1"}

    def test_far_hash_not_flagged(self):
        # All bits flipped -> distance 64, far beyond any sane threshold.
        recent_jobs = [{"id": "job1", "listing_id": "L1", "photo_hashes": ["0000000000000000"]}]
        result = find_duplicate(["ffffffffffffffff"], recent_jobs, max_distance=6)
        assert result is None

    def test_empty_new_hashes_no_match(self):
        recent_jobs = [{"id": "job1", "listing_id": "L1", "photo_hashes": ["abcd1234abcd1234"]}]
        assert find_duplicate([], recent_jobs, max_distance=6) is None

    def test_empty_recent_jobs_no_match(self):
        assert find_duplicate(["abcd1234abcd1234"], [], max_distance=6) is None

    def test_recent_job_missing_hashes_skipped_without_crash(self):
        recent_jobs = [{"id": "job1", "listing_id": "L1"}]
        assert find_duplicate(["abcd1234abcd1234"], recent_jobs, max_distance=6) is None

    def test_within_small_distance_flags_match(self):
        # Differ by exactly 1 bit.
        recent_jobs = [{"id": "job1", "listing_id": "L1", "photo_hashes": ["0000000000000000"]}]
        result = find_duplicate(["0000000000000001"], recent_jobs, max_distance=6)
        assert result == {"id": "job1", "listing_id": "L1"}

    # Multi-photo agreement: one coincidentally-similar angle must NOT flag a dup
    # (the "different Xerox parts, same background" false positive).
    Z = "0000000000000000"
    Y = "ffffffffffffffff"
    W = "00000000ffffffff"
    FAR1 = "aaaaaaaaaaaaaaaa"
    FAR2 = "5555555555555555"

    def test_single_matching_angle_among_many_not_flagged(self):
        new = [self.Z, self.Y, self.W]                       # 3 distinct photos
        recent_jobs = [{"id": "j", "listing_id": "L", "photo_hashes": [self.Z, self.FAR1, self.FAR2]}]
        # Only Z matches -> 1 of 3 -> below the 2-photo requirement -> not a dup.
        assert find_duplicate(new, recent_jobs, max_distance=6) is None

    def test_true_resend_all_photos_match_flags_dup(self):
        new = [self.Z, self.Y, self.W]
        recent_jobs = [{"id": "j", "listing_id": "L", "photo_hashes": [self.Z, self.Y, self.W]}]
        assert find_duplicate(new, recent_jobs, max_distance=6) == {"id": "j", "listing_id": "L"}

    def test_two_photo_item_needs_both_to_match(self):
        recent_one = [{"id": "j", "listing_id": "L", "photo_hashes": [self.Z, self.FAR1]}]
        assert find_duplicate([self.Z, self.Y], recent_one, max_distance=6) is None  # 1/2 -> no
        recent_both = [{"id": "j", "listing_id": "L", "photo_hashes": [self.Z, self.Y]}]
        assert find_duplicate([self.Z, self.Y], recent_both, max_distance=6) == {"id": "j", "listing_id": "L"}

    def test_required_matches_scaling(self):
        assert _required_matches(1, 0.6) == 1
        assert _required_matches(2, 0.6) == 2
        assert _required_matches(3, 0.6) == 2
        assert _required_matches(5, 0.6) == 3


# ---------------------------------------------------------------------------
# check_price_sanity
# ---------------------------------------------------------------------------

class TestCheckPriceSanity:
    def test_no_comp_high_price_flagged(self):
        reason = check_price_sanity(1091.99, "ai_estimate", [])
        assert reason is not None
        assert "1091" in reason or "review" in reason.lower() or "price" in reason.lower()

    def test_no_comp_low_price_not_flagged(self):
        assert check_price_sanity(29.99, "ai_estimate", []) is None

    def test_market_data_source_high_price_not_flagged_without_comps(self):
        # source starts with market_data -> condition (a) does not apply, and
        # comps is empty -> condition (b) does not apply either.
        assert check_price_sanity(500.0, "market_data_isbn", []) is None

    def test_price_over_3x_comp_median_flagged(self):
        comps = [{"price": 20.0}, {"price": 22.0}, {"price": 18.0}]
        # median = 20, 3x = 60
        reason = check_price_sanity(75.0, "market_data_isbn", comps)
        assert reason is not None

    def test_price_under_3x_comp_median_not_flagged(self):
        comps = [{"price": 20.0}, {"price": 22.0}, {"price": 18.0}]
        assert check_price_sanity(45.0, "market_data_isbn", comps) is None

    def test_research_market_price_source_no_comps_high_price_flagged(self):
        reason = check_price_sanity(200.0, "research_market_price", [])
        assert reason is not None

    def test_ai_grounded_research_source_no_comps_high_price_flagged(self):
        reason = check_price_sanity(151.0, "ai_grounded_research", [])
        assert reason is not None

    def test_threshold_boundary_not_flagged(self):
        assert check_price_sanity(150.0, "ai_estimate", []) is None


# ---------------------------------------------------------------------------
# apply_pre_listing_guardrails (orchestrator)
# ---------------------------------------------------------------------------

class FakeJob:
    """Minimal stand-in for QueueJob, just the fields guardrails touch."""

    def __init__(self, title, item_specifics, ai_data=None):
        self.title = title
        self.item_specifics = item_specifics
        self.ai_data = ai_data or {}


class TestApplyPreListingGuardrails:
    def test_clean_job_no_mutation_no_reason(self):
        job = FakeJob(
            title="Aiwa CSD-ES227 Stereo Boombox Cassette Player",
            item_specifics={"Brand": "Aiwa"},
            ai_data={"pricing_comps": [], "pricing_source": "market_data_isbn"},
        )
        original_title = job.title
        original_specifics = dict(job.item_specifics)
        result = apply_pre_listing_guardrails(job)
        assert result["review_reason"] is None
        assert job.title == original_title
        assert job.item_specifics == original_specifics

    def test_dirty_title_and_brand_autofixed_in_place(self):
        job = FakeJob(
            title="Duracell AA Batteries (Alkaline,",
            item_specifics={"Brand": "Signed"},
            ai_data={"pricing_comps": [], "pricing_source": "market_data_isbn"},
        )
        result = apply_pre_listing_guardrails(job)
        assert job.title == "Duracell AA Batteries"
        assert job.item_specifics["Brand"] == "Unbranded"
        assert result["review_reason"] is None

    def test_price_outlier_returns_review_reason(self):
        job = FakeJob(
            title="Vintage Shears",
            item_specifics={"Brand": "Unbranded"},
            ai_data={"pricing_comps": [], "pricing_source": "ai_estimate"},
        )
        result = apply_pre_listing_guardrails(job, price=1091.99, source="ai_estimate", comps=[])
        assert result["review_reason"] is not None

    def test_guard_exception_is_caught_and_job_proceeds(self, monkeypatch):
        import backend.app.services.listing_guardrails as guardrails_mod

        def _boom(title):
            raise RuntimeError("boom")

        monkeypatch.setattr(guardrails_mod, "clean_title", _boom)
        job = FakeJob(title="Anything", item_specifics={"Brand": "Sencore"})
        # Should not raise.
        result = apply_pre_listing_guardrails(job)
        assert result["review_reason"] is None


class TestConfidenceGate:
    """Low pricing confidence routes to review (under-price guard)."""

    def _job(self):
        return FakeJob(
            title="Rowenta Garment Steamer Handheld",
            item_specifics={"Brand": "Rowenta"},
            ai_data={"pricing_comps": [], "pricing_source": "market_data_keyword"},
        )

    def test_low_confidence_routes_to_review(self):
        result = apply_pre_listing_guardrails(
            self._job(), price=20.0, source="market_ai_conflict", comps=[],
            confidence="low",
            confidence_reason="comps say $12.18 but AI research says $99.99",
        )
        assert result["review_reason"] == "comps say $12.18 but AI research says $99.99"

    def test_low_confidence_without_reason_gets_default(self):
        result = apply_pre_listing_guardrails(
            self._job(), price=20.0, source="market_data_keyword", comps=[],
            confidence="low", confidence_reason=None,
        )
        assert result["review_reason"]

    def test_high_confidence_sane_price_no_review(self):
        result = apply_pre_listing_guardrails(
            self._job(), price=20.0, source="market_data_keyword",
            comps=[{"price": 18.0}, {"price": 20.0}, {"price": 22.0}],
            confidence="high", confidence_reason="5 comps, tight",
        )
        assert result["review_reason"] is None

    def test_user_confidence_never_reviews(self):
        result = apply_pre_listing_guardrails(
            self._job(), price=20.0, source="user_override", comps=[],
            confidence="user", confidence_reason=None,
        )
        assert result["review_reason"] is None

    def test_no_confidence_arg_backward_compatible(self):
        result = apply_pre_listing_guardrails(
            self._job(), price=20.0, source="market_data_keyword",
            comps=[{"price": 18.0}, {"price": 20.0}, {"price": 22.0}],
        )
        assert result["review_reason"] is None
