import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Let's scope the sys.modules patch to the import level to avoid polluting other tests.
# But because Python module caching can be tricky with patches (if it's imported once, 
# it stays in sys.modules, or if not, it throws later when referenced), we will use an 
# autouse fixture to patch `sys.modules` for all tests in this file.

@pytest.fixture(autouse=True)
def mock_dependencies():
    mock_modules = {
        'fire': MagicMock(),
        'yaml': MagicMock(),
        'dotenv': MagicMock(),
        'run_agent': MagicMock(),
        'tools.rl_training_tool': MagicMock()
    }
    with patch.dict('sys.modules', mock_modules):
        yield

def test_check_server_success(capsys):
    from rl_cli import main
    with patch("rl_cli.check_tinker_atropos", return_value=(True, {"path": "/fake/path", "environments_count": 5})):
        with patch("rl_cli.get_missing_keys", return_value=[]):
            main(check_server=True)
            captured = capsys.readouterr()
            assert "✅ tinker-atropos submodule found" in captured.out
            assert "Environments found: 5" in captured.out
            assert "✅ API keys configured" in captured.out

def test_check_server_failure_submodule(capsys):
    from rl_cli import main
    with patch("rl_cli.check_tinker_atropos", return_value=(False, "Not found")):
        main(check_server=True)
        captured = capsys.readouterr()
        assert "❌ tinker-atropos not set up: Not found" in captured.out

def test_check_server_missing_keys(capsys):
    from rl_cli import main
    with patch("rl_cli.check_tinker_atropos", return_value=(True, {"path": "/fake/path", "environments_count": 5})):
        with patch("rl_cli.get_missing_keys", return_value=["WANDB_API_KEY"]):
            main(check_server=True)
            captured = capsys.readouterr()
            assert "✅ tinker-atropos submodule found" in captured.out
            assert "⚠️  Missing API keys: WANDB_API_KEY" in captured.out
