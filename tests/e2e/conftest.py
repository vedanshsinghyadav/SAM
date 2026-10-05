"""
Pytest configuration and global fixtures for Project SAM E2E tests.
"""

import pytest
from tests.e2e.fixtures import TempWorkspace, create_test_system
from tests.e2e.harness import SAMSystemFacade, BrainEngineAdapter, MemoryEngineAdapter, ComputerControllerAdapter


@pytest.fixture
def workspace():
    """Provides a fresh isolated temporary workspace."""
    ws = TempWorkspace()
    yield ws
    ws.cleanup()


@pytest.fixture
def sam_system(workspace):
    """Provides an initialized SAMSystemFacade instance connected to workspace."""
    sys_facade = create_test_system(workspace_root=workspace.root)
    yield sys_facade
    sys_facade.close()


@pytest.fixture
def brain():
    """Provides a fresh BrainEngineAdapter."""
    return BrainEngineAdapter()


@pytest.fixture
def memory():
    """Provides a fresh isolated MemoryEngineAdapter."""
    mem = MemoryEngineAdapter()
    yield mem
    mem.close()


@pytest.fixture
def controller(workspace):
    """Provides a ComputerControllerAdapter pointing to isolated workspace."""
    return ComputerControllerAdapter(workspace_root=workspace.root)
