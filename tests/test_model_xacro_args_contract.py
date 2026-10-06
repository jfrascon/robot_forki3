from pathlib import Path
import re

import pytest
import yaml

from conftest import PACKAGE_DIR

RUNTIME_XACRO_ARGS = {'namespace', 'robot_name', 'sim_file'}


def _xacro_arg_defaults(path: Path) -> dict[str, str]:
    source = path.read_text(encoding='utf-8')
    return dict(re.findall(r'<xacro:arg\s+name="([^"]+)"\s+default="([^"]*)"', source))


def _normalize_scalar(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_default_model_xacro_args_match_the_xacro_contract(robot_model: str) -> None:
    common_defaults = _xacro_arg_defaults(PACKAGE_DIR / 'urdf' / 'common.xacro')
    fork_defaults = _xacro_arg_defaults(PACKAGE_DIR / 'urdf' / 'fork_macro.xacro')
    model_defaults = {**common_defaults, **fork_defaults}

    if robot_model == 'a':
        sensor_defaults = _xacro_arg_defaults(PACKAGE_DIR / 'urdf' / 'robot_forki3_a.xacro')
        model_defaults = {**common_defaults, **fork_defaults, **sensor_defaults}

    expected_defaults = {
        name: value for name, value in model_defaults.items() if name not in RUNTIME_XACRO_ARGS
    }
    args_path = PACKAGE_DIR / 'config' / f'model_{robot_model}' / 'default_xacro_args.yaml'
    configured_defaults = yaml.safe_load(args_path.read_text(encoding='utf-8'))

    assert isinstance(configured_defaults, dict)
    assert set(configured_defaults) == set(expected_defaults)

    for name, expected in expected_defaults.items():
        assert _normalize_scalar(configured_defaults[name]).lower() == expected.lower()


def test_legacy_xargs_contract_is_removed() -> None:
    xargs_dir = PACKAGE_DIR / 'xargs'

    assert not list(xargs_dir.glob('*.yaml'))


@pytest.mark.parametrize(
    'sensor, expected_mount',
    [
        ('front_top_lidar', '-0.07647355 0 1.786 0 0 0'),
        ('back_bottom_lidar', '-0.692435 0 0.019941 0 0 3.141592653589793'),
    ],
)
def test_sensor_mounts_are_model_properties(sensor: str, expected_mount: str) -> None:
    model_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_a.xacro'
    source = model_path.read_text(encoding='utf-8')
    mount_name = f'{sensor}_mount'

    assert mount_name not in _xacro_arg_defaults(model_path)
    assert f'$(arg {mount_name})' not in source
    assert re.search(
        rf'<xacro:property\s+name="{mount_name}"\s+value="{re.escape(expected_mount)}"', source
    )
