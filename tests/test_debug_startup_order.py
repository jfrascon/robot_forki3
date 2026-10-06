"""Validate the world and model readiness gates used by both Forki3 debug models."""

import importlib.util
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

from launch import LaunchContext
from launch import LaunchDescription
from launch.actions import EmitEvent
from launch.actions import IncludeLaunchDescription
from launch.actions import OpaqueFunction
from launch.actions import RegisterEventHandler
from launch.utilities import normalize_to_list_of_substitutions
from launch.utilities import perform_substitutions
from launch_ros.actions import Node
import pytest

from conftest import PACKAGE_DIR


def _load_debug(model: str) -> ModuleType:
    """Load one debug entry point without starting ROS or Gazebo processes."""
    path = PACKAGE_DIR.joinpath('launch', f'debug_robot_forki3_{model}.launch.py')
    spec = importlib.util.spec_from_file_location(f'debug_{model}', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('model', ['base', 'a'])
def test_debug_launch_creates_from_urdf_then_starts_robot_nodes(
    model: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wait for the selected world and spawn from the shared file before constructing nodes."""
    module = _load_debug(model)
    ctx = LaunchContext()
    urdf_file = tmp_path.joinpath('robot.urdf')
    urdf_file.write_text('<robot name="forki3"/>', encoding='utf-8')
    ctx.launch_configurations.update(
        {
            'world_name': 'selected_world',
            'namespace': '/sim_debug',
            'project_namespace': '/sim_debug',
            'robot_name': 'forki3',
            'robot_urdf_file': str(urdf_file),
            'robot_description_topic': 'robot_description',
            'robot_rsp_node_args': '{}',
            'resolved_robot_params_file': str(
                PACKAGE_DIR.joinpath('config', f'model_{model}', 'default_params.yaml')
            ),
            'use_sim_time': 'True',
            'robot_bridge_config_file': str(
                PACKAGE_DIR.joinpath('config', f'model_{model}', 'default_bridge.yaml')
            ),
            'robot_bridge_node_args': '{}',
            'robot_kinematics_node_args': '{}',
            'robot_fork_controller_node_args': '{}',
            'robot_fork_serial_node_args': '{}',
        }
    )
    captured = {}
    process_factory = module.ExecuteProcess
    node_factory = module.Node

    def create_process(**kwargs):
        """Capture the service-wait command while preserving the event handler's real target."""
        captured['wait_cmd'] = kwargs['cmd']
        return process_factory(**kwargs)

    def create_node(**kwargs):
        """Capture the create node's input while preserving its process-exit handler target."""
        if kwargs.get('executable') == 'create':
            captured['node_parameters'] = kwargs['parameters']
        return node_factory(**kwargs)

    monkeypatch.setattr(module, 'ExecuteProcess', create_process)
    monkeypatch.setattr(module, 'Node', create_node)
    actions = module.generate_launch_description().entities
    assert isinstance(actions[-2], RegisterEventHandler)
    assert len([action for action in actions if isinstance(action, OpaqueFunction)]) == 1
    includes = [action for action in actions if isinstance(action, IncludeLaunchDescription)]
    paths = []
    for include in includes:
        include.launch_description_source.get_launch_description(ctx)
        paths.append(Path(include.launch_description_source.location).name)
    assert paths == ['render_robot_urdf.launch.py', 'spawn_world.launch.py']
    command = [
        perform_substitutions(ctx, normalize_to_list_of_substitutions(value))
        for value in captured['wait_cmd']
    ]
    assert Path(command[0]).name == 'wait_for_gz_service.py'
    assert command[1] == '/world/selected_world/create'
    ready = SimpleNamespace(returncode=0)
    spawned = module._launch_actions_after_world_ready(ready, ctx)
    assert isinstance(spawned[0], RegisterEventHandler)
    assert isinstance(spawned[-1], Node)
    parameters = captured['node_parameters'][0]
    assert parameters['file'].perform(ctx) == str(urdf_file)
    assert parameters['world'].perform(ctx) == 'selected_world'
    assert parameters['topic'] == ''
    assert parameters['string'] == ''
    started = module._launch_actions_after_model_ready(ready, ctx)
    assert len(started) == 5
    assert isinstance(started[0], IncludeLaunchDescription)
    rsp = started[0]
    arguments = dict(rsp.launch_arguments)
    assert perform_substitutions(
        ctx, normalize_to_list_of_substitutions(arguments['robot_urdf_file'])
    ) == str(urdf_file)
    assert all(isinstance(action, IncludeLaunchDescription) for action in started[1:4])
    assert isinstance(started[-1], Node)
    nodes = []

    def expand(action) -> None:
        """Resolve child node configuration in the shared context without running processes."""
        if isinstance(action, Node):
            action._perform_substitutions(ctx)
            nodes.append(action)
            return
        children = action.entities if isinstance(action, LaunchDescription) else action.visit(ctx)
        for child in children or []:
            expand(child)

    for action in started[:-1]:
        expand(action)
    assert len(nodes) == 4
    assert all(node.expanded_node_namespace == '/sim_debug/forki3' for node in nodes)


@pytest.mark.parametrize('model', ['base', 'a'])
@pytest.mark.parametrize(
    'phase', ['_launch_actions_after_world_ready', '_launch_actions_after_model_ready']
)
def test_failed_readiness_phase_stops_without_starting_robot_nodes(model: str, phase: str) -> None:
    """Stop the launch after a failed world readiness check or failed model creation."""
    module = _load_debug(model)
    actions = getattr(module, phase)(SimpleNamespace(returncode=1), LaunchContext())
    assert len(actions) == 1
    assert isinstance(actions[0], EmitEvent)
