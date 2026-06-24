#!/usr/bin/env python3
"""Tests for Colossus DevOps Pipeline — LIVE"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.devops_pipeline import (
    DevOpsPipeline, PipelineRun, PipelineStage, GateResult, GateCheck
)


@pytest.fixture
def pipeline():
    return DevOpsPipeline()


class TestDevOpsPipeline:
    def test_pro_code_gates_defined(self, pipeline):
        assert len(pipeline.PRO_CODE_GATES) == 7

    def test_repos_registered(self, pipeline):
        assert len(pipeline.REPOS) == 4
        assert "xai-colossus-2" in pipeline.REPOS

    @pytest.mark.asyncio
    async def test_pipeline_validates_structure(self, pipeline):
        run = await pipeline.run_pipeline("xai-colossus-2")
        assert run.stage == PipelineStage.COMPLETE
        # Should have validation gates
        validation_gates = [g for g in run.gates if "file_" in g.gate_name]
        assert len(validation_gates) >= 2

    @pytest.mark.asyncio
    async def test_pipeline_runs_pytest(self, pipeline):
        run = await pipeline.run_pipeline("xai-colossus-2")
        pytest_gates = [g for g in run.gates if g.gate_name == "pytest"]
        assert len(pytest_gates) == 1
        assert pytest_gates[0].result in (GateResult.PASS, GateResult.FAIL)
        assert run.tests_passed > 0

    @pytest.mark.asyncio
    async def test_pipeline_audits_code(self, pipeline):
        run = await pipeline.run_pipeline("xai-colossus-cooling")
        audit_gates = [g for g in run.gates if g.gate_name in pipeline.PRO_CODE_GATES]
        assert len(audit_gates) == 7

    @pytest.mark.asyncio
    async def test_run_all_pipelines(self, pipeline):
        results = await pipeline.run_all_pipelines()
        assert len(results) == 4
        passed = [r for r in results if r.stage == PipelineStage.COMPLETE]
        assert len(passed) >= 3  # At least 3 should pass

    def test_report_structure(self, pipeline):
        report = pipeline.generate_report()
        assert "total_runs" in report
        assert "runs" in report
        assert "summary" in report
