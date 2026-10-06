import importlib.util
from pathlib import Path
from types import ModuleType
import xml.etree.ElementTree as ET

from launch import LaunchContext
from launch.utilities import normalize_to_list_of_substitutions
from launch.utilities import perform_substitutions
import pytest
import yaml

from conftest import PACKAGE_DIR


def _load_launch_module() -> ModuleType:
    path = PACKAGE_DIR.joinpath('launch', 'render_robot_urdf.launch.py')
    spec = importlib.util.spec_from_file_location('robot_forki3_render_robot_urdf_launch', path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_xacro_command_accepts_file_uri_for_optional_arguments() -> None:
    module = _load_launch_module()
    xacro_file = PACKAGE_DIR / 'urdf' / 'robot_forki3_base.xacro'
    xacro_args_file = PACKAGE_DIR / 'config' / 'model_base' / 'default_xacro_args.yaml'

    command = module._build_xacro_command(str(xacro_file), xacro_args_file.as_uri(), '')

    assert any('body_color:=' in token for token in command if isinstance(token, str))


def test_quote_shell_token_uses_shell_quoting_when_needed() -> None:
    module = _load_launch_module()

    assert module._quote_shell_token('plain_value') == 'plain_value'
    assert module._quote_shell_token('') == "''"
    assert module._quote_shell_token('value with spaces') == "'value with spaces'"
    assert module._quote_shell_token('value "with quotes"') == '\'value "with quotes"\''


def test_build_xacro_command_quotes_paths_and_complete_yaml_assignments(tmp_path: Path) -> None:
    module = _load_launch_module()
    xacro_file = tmp_path / 'model files' / 'robot_forki3_base.xacro'
    xacro_args_file = tmp_path / 'model args.yaml'
    xacro_file.parent.mkdir()
    xacro_file.touch()
    xacro_args_file.write_text(
        yaml.safe_dump({'custom arg': 'value with spaces'}), encoding='utf-8'
    )

    command = module._build_xacro_command(str(xacro_file), str(xacro_args_file), '')

    assert f"'{xacro_file}'" in command
    assert "'custom arg:=value with spaces'" in command


@pytest.mark.parametrize('runtime_argument', ['namespace', 'robot_name', 'sim_file'])
def test_xacro_args_file_rejects_launch_owned_argument(
    runtime_argument: str, tmp_path: Path
) -> None:
    module = _load_launch_module()
    args_file = tmp_path / 'xacro_args.yaml'
    args_file.write_text(yaml.safe_dump({runtime_argument: 'invalid'}), encoding='utf-8')

    with pytest.raises(ValueError, match=runtime_argument):
        module._load_xacro_args(str(args_file))


def test_xacro_args_file_requires_a_top_level_mapping(tmp_path: Path) -> None:
    module = _load_launch_module()
    args_file = tmp_path / 'xacro_args.yaml'
    args_file.write_text('- invalid\n', encoding='utf-8')

    with pytest.raises(TypeError, match='mapping'):
        module._load_xacro_args(str(args_file))


@pytest.mark.parametrize('model', ['base', 'a'])
def test_debug_renderer_and_state_publisher_share_exact_urdf(
    model: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Render each debug model and verify RSP receives the completed file's exact XML."""
    renderer = _load_launch_module()
    modules = {}
    for role, filename in (
        ('debug', f'debug_robot_forki3_{model}.launch.py'),
        ('rsp', 'robot_state_publisher.launch.py'),
    ):
        spec = importlib.util.spec_from_file_location(
            role, PACKAGE_DIR.joinpath('launch', filename)
        )
        assert spec is not None and spec.loader is not None
        modules[role] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modules[role])
    debug = modules['debug']
    rsp = modules['rsp']
    ctx = LaunchContext()
    ctx.launch_configurations.update(
        {
            'namespace': '/sim_debug',
            'project_namespace': '/sim_debug',
            'robot_name': 'forki3',
            'robot_namespace': '/sim_debug/forki3',
            'robot_description_topic': 'robot_description',
            'robot_rsp_node_args': '{}',
            'robot_xacro_args_file': str(
                PACKAGE_DIR.joinpath('config', f'model_{model}', 'default_xacro_args.yaml')
            ),
            'robot_sim_file': str(
                PACKAGE_DIR.joinpath('config', f'model_{model}', 'default_simulation.yaml')
            ),
            'resolved_robot_params_file': str(
                PACKAGE_DIR.joinpath('config', f'model_{model}', 'default_params.yaml')
            ),
            'use_sim_time': 'True',
        }
    )
    debug.generate_launch_description()
    debug._set_robot_urdf_file(ctx)
    urdf_file = Path(ctx.launch_configurations['robot_urdf_file'])
    captured = {}

    class FakeNode:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(rsp, 'Node', FakeNode)
    try:
        render_args = {
            key: perform_substitutions(ctx, normalize_to_list_of_substitutions(value))
            for key, value in debug._include_render_robot_urdf().launch_arguments
        }
        ctx.launch_configurations.update(render_args)
        renderer._render_robot_urdf(ctx)
        xml = urdf_file.read_text(encoding='utf-8')
        assert ET.fromstring(xml).tag == 'robot'
        rsp_args = {
            key: perform_substitutions(ctx, normalize_to_list_of_substitutions(value))
            for key, value in debug._include_robot_state_publisher(ctx).launch_arguments
        }
        assert rsp_args['robot_urdf_file'] == render_args['robot_urdf_file']
        assert 'robot_xacro_file' not in rsp_args
        assert 'robot_sim_file' not in rsp_args
        ctx.launch_configurations.update(rsp_args)
        rsp._launch_node(ctx)
        description = captured['parameters'][1]['robot_description'].evaluate(ctx)
        assert description == xml
    finally:
        urdf_file.unlink(missing_ok=True)
