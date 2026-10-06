import os

import pytest

from conftest import PACKAGE_DIR
from conftest import run_bash


@pytest.mark.parametrize('script_name', ['debug_robot_forki3_base.sh', 'debug_robot_forki3_a.sh'])
def test_debug_script_is_executable_and_has_valid_bash_syntax(script_name: str) -> None:
    script_path = PACKAGE_DIR / 'scripts' / script_name

    assert os.access(script_path, os.X_OK)

    result = run_bash(f'bash -n "{script_path}"')
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
