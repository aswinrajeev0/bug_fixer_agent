from pathlib import Path
from unittest.mock import MagicMock
from healcode.config import HealConfig
from healcode.core.loop import HealingLoop
from healcode.agent.models import HealingProposal, FilePatch
from healcode.agent.gemini_client import GeminiAgent
from healcode.runners.base import BaseTestRunner, TestRunResult, TestCaseResult, TestStatus

class MockRunner(BaseTestRunner):
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.call_count = 0

    def run_tests(self, target=None) -> TestRunResult:
        self.call_count += 1
        # Check if calculator.py has been fixed
        calc_file = self.work_dir / "calc.py"
        content = calc_file.read_text() if calc_file.exists() else ""

        if "return a + b" in content:
            # Fixed!
            return TestRunResult(
                success=True,
                exit_code=0,
                passed_count=1,
                failed_count=0,
            )
        else:
            # Failing!
            return TestRunResult(
                success=False,
                exit_code=1,
                failed_count=1,
                failures=[
                    TestCaseResult(
                        name="test_add",
                        status=TestStatus.FAILED,
                        file_path="test_calc.py",
                        line_number=4,
                        message="AssertionError: assert 0 == 5",
                        traceback="File \"calc.py\", line 2, in add\n    return 0\nAssertionError: assert 0 == 5",
                    )
                ],
            )

def test_healing_loop_end_to_end_mock(tmp_path):
    # Setup test workspace
    calc_path = tmp_path / "calc.py"
    calc_path.write_text("def add(a, b):\n    return 0\n")

    test_path = tmp_path / "test_calc.py"
    test_path.write_text("from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")

    mock_agent = MagicMock(spec=GeminiAgent)
    mock_agent.generate_healing_proposal.return_value = HealingProposal(
        root_cause_analysis="Function add returns 0 instead of sum.",
        fix_hypothesis="Change return statement to return a + b.",
        patches=[
            FilePatch(
                file_path="calc.py",
                description="Fix addition logic",
                new_content="def add(a, b):\n    return a + b\n",
            )
        ],
        confidence_score=0.99,
        risk_assessment="None",
    )

    runner = MockRunner(tmp_path)
    config = HealConfig(
        target_dir=tmp_path,
        max_retries=2,
        git_checkpoint=False,
        interactive=False,
    )

    loop = HealingLoop(config=config, runner=runner, agent=mock_agent)
    state = loop.run()

    assert state.is_healed is True
    assert calc_path.read_text() == "def add(a, b):\n    return a + b\n"
    assert len(state.iterations) == 1
    assert state.iterations[0].success is True
