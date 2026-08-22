#!/usr/bin/env python3
"""Tests for Colossus DevOps Pipeline — LIVE"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.devops_pipeline import (
    DevOpsPipeline, PipelineStage, GateResult
)


@pytest.fixture
def pipeline():
    return DevOpsPipeline()


def _has_repo(pipeline, name: str) -> bool:
    path = pipeline.REPOS.get(name)
    return bool(path and path.exists())


class TestDevOpsPipeline:
    def test_pro_code_gates_defined(self, pipeline):
        assert len(pipeline.PRO_CODE_GATES) == 7

    def test_repos_registered(self, pipeline):
        assert len(pipeline.REPOS) == 4
        assert "xai-colossus-2" in pipeline.REPOS

    def test_pipeline_validates_structure(self, pipeline):
        if not _has_repo(pipeline, "xai-colossus-2"):
            pytest.skip("xai-colossus-2 not checked out beside this repo")
        run = asyncio.run(pipeline.run_pipeline("xai-colossus-2"))
        assert run.stage == PipelineStage.COMPLETE
        validation_gates = [g for g in run.gates if "file_" in g.gate_name]
        assert len(validation_gates) >= 2

    def test_pipeline_runs_pytest(self, pipeline):
        if not _has_repo(pipeline, "xai-colossus-2"):
            pytest.skip("xai-colossus-2 not checked out beside this repo")
        run = asyncio.run(pipeline.run_pipeline("xai-colossus-2"))
        pytest_gates = [g for g in run.gates if g.gate_name == "pytest"]
        assert len(pytest_gates) == 1
        assert pytest_gates[0].result in (GateResult.PASS, GateResult.FAIL)
        assert run.tests_passed > 0

    def test_pipeline_audits_code(self, pipeline):
        if not _has_repo(pipeline, "xai-colossus-cooling"):
            pytest.skip("sibling xai-colossus-cooling not present in this checkout")
        run = asyncio.run(pipeline.run_pipeline("xai-colossus-cooling"))
        audit_gates = [g for g in run.gates if g.gate_name in pipeline.PRO_CODE_GATES]
        assert len(audit_gates) == 7

    def test_run_all_pipelines(self, pipeline):
        present = [name for name in pipeline.REPOS if _has_repo(pipeline, name)]
        if len(present) < 3:
            pytest.skip("sibling Colossus repos not present; isolated checkout")
        results = asyncio.run(pipeline.run_all_pipelines())
        assert len(results) == 4
        passed = [r for r in results if r.stage == PipelineStage.COMPLETE]
        assert len(passed) >= 3

    def test_report_structure(self, pipeline):
        report = pipeline.generate_report()
        assert "total_runs" in report
        assert "runs" in report
        assert "summary" in report
