#!/usr/bin/env python3
"""Tests for Colossus Mastermind Orchestrator"""
import asyncio
import pytest
from core.mastermind_orchestrator import (
    MastermindOrchestrator, Task, TaskPriority, TaskState, Piston
)


@pytest.fixture
def orchestrator():
    return MastermindOrchestrator()


class TestMastermindOrchestrator:
    def test_initial_pistons_registered(self, orchestrator):
        assert len(orchestrator.pistons) == 12

    def test_piston_health(self, orchestrator):
        piston = orchestrator.pistons["stealth_microwave"]
        assert piston.health == 1.0  # No tasks yet

    @pytest.mark.asyncio
    async def test_submit_task(self, orchestrator):
        task = Task(
            task_id="T1",
            description="Test task",
            priority=TaskPriority.P2_MEDIUM,
        )
        task_id = await orchestrator.submit_task(task)
        assert task_id == "T1"
        assert len(orchestrator.tasks) == 1

    @pytest.mark.asyncio
    async def test_assign_task(self, orchestrator):
        task = Task(
            task_id="T1",
            description="Parallel batch processing",
            priority=TaskPriority.P1_HIGH,
        )
        piston_id = orchestrator.assign_task(task)
        assert piston_id is not None
        assert task.state == TaskState.ASSIGNED

    @pytest.mark.asyncio
    async def test_chain_tasks(self, orchestrator):
        tasks = [
            Task(f"T{i}", f"Task {i}", TaskPriority.P2_MEDIUM)
            for i in range(3)
        ]
        task_ids = await orchestrator.chain_tasks(tasks)
        assert len(task_ids) == 3
        assert len(orchestrator.chain_history) == 1

    @pytest.mark.asyncio
    async def test_run_task(self, orchestrator):
        task = Task(
            task_id="T1",
            description="Test execution",
            priority=TaskPriority.P2_MEDIUM,
        )
        orchestrator.assign_task(task)
        result = await orchestrator.run_task(task)
        assert result["status"] == "completed"
        assert task.state == TaskState.COMPLETED

    def test_summary_structure(self, orchestrator):
        s = orchestrator.summary()
        assert "tick_count" in s
        assert "total_tasks" in s
        assert "pistons" in s
        assert len(s["pistons"]) == 12
