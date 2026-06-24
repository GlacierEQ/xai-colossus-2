#!/usr/bin/env python3
"""Tests for Colossus DevOps Pipeline"""
import asyncio
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
        assert "naming" in pipeline.PRO_CODE_GATES
        assert "architecture" in pipeline.PRO_CODE_GATES

    @pytest.mark.asyncio
    async def test_pipeline_runs(self, pipeline):
        run = await pipeline.run_pipeline("test-repo")
        assert run.stage == PipelineStage.COMPLETE
        # WARN gates are acceptable (non-blocking)
        assert all(g.result in (GateResult.PASS, GateResult.WARN) for g in run.gates)

    def test_report_structure(self, pipeline):
        run = PipelineRun(run_id="test", repo="test", branch="main")
        report = pipeline.generate_report(run)
        assert "run_id" in report
        assert "gates" in report
        assert "all_gates_pass" in report

    def test_gate_check(self, pipeline):
        gate = GateCheck("naming", GateResult.PASS, "snake_case verified")
        assert gate.gate_name == "naming"
        assert gate.result == GateResult.PASS
