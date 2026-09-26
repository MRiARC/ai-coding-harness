"""Agent contracts: base classes, task value objects (specialist roles land in milestone 2)."""

from harness.agents.base import BaseAgent, BaseManager, ContextWindow
from harness.agents.task import Task, TaskResult

__all__ = ["BaseAgent", "BaseManager", "ContextWindow", "Task", "TaskResult"]
