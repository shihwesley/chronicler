"""Tests for type invariant enforcement (REQ-1 through REQ-8)."""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import ValidationError

from chronicler_core.config.models import (
    DocumentConversionConfig,
    LLMSettings,
    QueueConfig,
    VCSConfig,
)
from chronicler_core.drafter.models import FrontmatterModel, GovernanceModel, TechDoc
from chronicler_core.interfaces.queue import Job
from chronicler_core.llm.models import LLMConfig
from chronicler_core.merkle.models import MerkleDiff, MerkleNode
from chronicler_core.vcs.models import RepoMetadata


# ── REQ-1: VCSConfig mutable default ──────────────────────────────────


class TestVCSConfigMutableDefault:
    def test_separate_list_instances(self):
        """Two VCSConfig instances must not share the same list object."""
        a = VCSConfig()
        b = VCSConfig()
        assert a.allowed_orgs is not b.allowed_orgs

    def test_mutating_one_does_not_affect_other(self):
        a = VCSConfig()
        b = VCSConfig()
        a.allowed_orgs.append("acme")
        assert b.allowed_orgs == []


# ── REQ-2: Empty component_id / id rejected ──────────────────────────


class TestComponentIdValidation:
    def test_techdoc_empty_component_id_rejected(self):
        with pytest.raises(ValidationError):
            TechDoc(component_id="", frontmatter=FrontmatterModel(component_id="x"))

    def test_techdoc_whitespace_component_id_rejected(self):
        with pytest.raises(ValidationError):
            TechDoc(component_id="   ", frontmatter=FrontmatterModel(component_id="x"))

    def test_repo_metadata_empty_component_id_rejected(self):
        with pytest.raises(ValidationError):
            RepoMetadata(
                component_id="", name="x", full_name="x",
            )

    def test_repo_metadata_whitespace_component_id_rejected(self):
        with pytest.raises(ValidationError):
            RepoMetadata(
                component_id="   ", name="x", full_name="x",
            )

    def test_job_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            Job(id="", payload={})

    def test_job_whitespace_id_rejected(self):
        with pytest.raises(ValidationError):
            Job(id="   ", payload={})

    def test_frontmatter_empty_component_id_rejected(self):
        with pytest.raises(ValidationError):
            FrontmatterModel(component_id="")


# ── REQ-3: Numeric config bounds ─────────────────────────────────────


class TestNumericBounds:
    def test_llm_settings_negative_max_tokens(self):
        with pytest.raises(ValidationError):
            LLMSettings(max_tokens=-1)

    def test_llm_settings_zero_timeout(self):
        with pytest.raises(ValidationError):
            LLMSettings(timeout=0)

    def test_llm_settings_negative_retry_delay(self):
        with pytest.raises(ValidationError):
            LLMSettings(retry_delay=-0.5)

    def test_llm_settings_negative_max_retries_rejected(self):
        with pytest.raises(ValidationError):
            LLMSettings(max_retries=-1)

    def test_llm_settings_zero_max_retries_allowed(self):
        cfg = LLMSettings(max_retries=0)
        assert cfg.max_retries == 0

    def test_llm_config_negative_max_tokens(self):
        with pytest.raises(ValidationError):
            LLMConfig(provider="anthropic", model="test", max_tokens=-1)

    def test_llm_config_temperature_too_high(self):
        with pytest.raises(ValidationError):
            LLMConfig(provider="anthropic", model="test", temperature=5.0)

    def test_llm_config_temperature_negative(self):
        with pytest.raises(ValidationError):
            LLMConfig(provider="anthropic", model="test", temperature=-0.1)

    def test_llm_config_temperature_at_boundary(self):
        cfg = LLMConfig(provider="anthropic", model="test", temperature=2.0)
        assert cfg.temperature == 2.0
        cfg2 = LLMConfig(provider="anthropic", model="test", temperature=0.0)
        assert cfg2.temperature == 0.0

    def test_queue_config_zero_max_workers(self):
        with pytest.raises(ValidationError):
            QueueConfig(max_workers=0)

    def test_queue_config_zero_visibility_timeout(self):
        with pytest.raises(ValidationError):
            QueueConfig(visibility_timeout=0)

    def test_doc_conversion_zero_max_file_size(self):
        with pytest.raises(ValidationError):
            DocumentConversionConfig(max_file_size_mb=0)

    def test_job_negative_attempts_rejected(self):
        with pytest.raises(ValidationError):
            Job(id="j-1", payload={}, attempts=-1)


# ── REQ-4: MerkleNode.hash validation ────────────────────────────────


class TestMerkleNodeHashValidation:
    def test_valid_12_char_hex(self):
        node = MerkleNode(path="x", hash="aabbccddeeff")
        assert node.hash == "aabbccddeeff"

    def test_invalid_hash_not_hex(self):
        with pytest.raises(ValueError, match="12-char hex"):
            MerkleNode(path="x", hash="nothex")

    def test_invalid_hash_wrong_length(self):
        with pytest.raises(ValueError, match="12-char hex"):
            MerkleNode(path="x", hash="aabb")

    def test_invalid_hash_uppercase_rejected(self):
        with pytest.raises(ValueError, match="12-char hex"):
            MerkleNode(path="x", hash="AABBCCDDEEFF")

    def test_empty_hash_rejected(self):
        with pytest.raises(ValueError, match="12-char hex"):
            MerkleNode(path="x", hash="")


# ── REQ-5: FrontmatterModel ──────────────────────────────────────────


class TestFrontmatterModel:
    def test_has_required_component_id(self):
        fm = FrontmatterModel(component_id="test/app")
        assert fm.component_id == "test/app"

    def test_has_version_default(self):
        fm = FrontmatterModel(component_id="x")
        assert fm.version == "0.1.0"

    def test_has_layer_default(self):
        fm = FrontmatterModel(component_id="x")
        assert fm.layer == "unknown"

    def test_governance_is_model(self):
        fm = FrontmatterModel(component_id="x")
        assert isinstance(fm.governance, GovernanceModel)
        assert fm.governance.verification_status == "ai_draft"

    def test_techdoc_frontmatter_is_model(self):
        fm = FrontmatterModel(component_id="x")
        doc = TechDoc(component_id="x", frontmatter=fm)
        assert isinstance(doc.frontmatter, FrontmatterModel)

    def test_model_dump_roundtrip(self):
        fm = FrontmatterModel(component_id="test/app", version="1.0", layer="api")
        data = fm.model_dump()
        restored = FrontmatterModel(**data)
        assert restored == fm


# ── REQ-6: No duplicate LLMConfig names ──────────────────────────────


class TestLLMConfigDisambiguation:
    def test_config_models_has_llm_settings(self):
        from chronicler_core.config import models as config_models
        assert hasattr(config_models, "LLMSettings")
        assert not hasattr(config_models, "LLMConfig")

    def test_llm_models_has_llm_config(self):
        from chronicler_core.llm import models as llm_models
        assert hasattr(llm_models, "LLMConfig")


# ── REQ-7: Frozen MerkleNode / MerkleDiff ────────────────────────────


class TestFrozenMerkle:
    def test_merkle_node_frozen(self):
        node = MerkleNode(path="x", hash="aabbccddeeff")
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.hash = "112233445566"

    def test_merkle_node_path_frozen(self):
        node = MerkleNode(path="x", hash="aabbccddeeff")
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.path = "y"

    def test_merkle_diff_frozen(self):
        diff = MerkleDiff()
        with pytest.raises(dataclasses.FrozenInstanceError):
            diff.root_changed = True

    def test_merkle_node_children_is_tuple(self):
        node = MerkleNode(path="x", hash="aabbccddeeff", children=("a", "b"))
        assert isinstance(node.children, tuple)


# ── REQ-8: RepoMetadata.url validation ───────────────────────────────


class TestRepoMetadataUrlValidation:
    def test_valid_https_url(self):
        meta = RepoMetadata(
            component_id="test/repo", name="repo", full_name="test/repo",
            url="https://github.com/test/repo",
        )
        assert meta.url == "https://github.com/test/repo"

    def test_valid_http_url(self):
        meta = RepoMetadata(
            component_id="test/repo", name="repo", full_name="test/repo",
            url="http://example.com/repo",
        )
        assert meta.url == "http://example.com/repo"

    def test_empty_url_allowed(self):
        meta = RepoMetadata(
            component_id="test/repo", name="repo", full_name="test/repo",
            url="",
        )
        assert meta.url == ""

    def test_ftp_url_rejected(self):
        with pytest.raises(ValidationError):
            RepoMetadata(
                component_id="test/repo", name="repo", full_name="test/repo",
                url="ftp://files.example.com/repo",
            )

    def test_bare_string_url_rejected(self):
        with pytest.raises(ValidationError):
            RepoMetadata(
                component_id="test/repo", name="repo", full_name="test/repo",
                url="not-a-url",
            )
