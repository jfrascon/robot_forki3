"""Render a Forki3 Xacro entry point to a reusable URDF file."""

from pathlib import Path
import shlex
from tempfile import NamedTemporaryFile
from typing import Any

from launch import LaunchContext
from launch import LaunchDescription
from launch import LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument
from launch.actions import LogInfo
from launch.actions import OpaqueFunction
from launch.substitutions import Command
from launch.substitutions import FindExecutable
from launch.substitutions import LaunchConfiguration
import ros2_launch_helpers as rlh


def generate_launch_description() -> LaunchDescription:
    """Declare the reusable Forki3 Xacro-to-URDF launch interface."""
    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
            DeclareLaunchArgument(
                'robot_xacro_file',
                description='Path to the Xacro file that generates the robot URDF.',
            ),
            DeclareLaunchArgument(
                'robot_xacro_args_file',
                default_value='',
                description='Path or URI to the YAML file with model Xacro arguments.',
            ),
            DeclareLaunchArgument(
                'robot_sim_file',
                default_value='',
                description='Optional simulation YAML. Empty omits simulation plugins.',
            ),
            DeclareLaunchArgument(
                'robot_urdf_file', description='Path where the rendered robot URDF is written.'
            ),
            rlh.RequireFile(path=LaunchConfiguration('robot_xacro_file')),
            OpaqueFunction(function=_render_robot_urdf),
            rlh.RequireFile(path=LaunchConfiguration('robot_urdf_file')),
        ]
    )


def _render_robot_urdf(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """Render the requested Xacro and atomically replace the requested URDF output."""
    xacro_file = LaunchConfiguration('robot_xacro_file').perform(ctx).strip()
    xacro_args_file = LaunchConfiguration('robot_xacro_args_file').perform(ctx).strip()
    sim_file = LaunchConfiguration('robot_sim_file').perform(ctx).strip()
    urdf_file = LaunchConfiguration('robot_urdf_file').perform(ctx).strip()

    if not urdf_file:
        raise ValueError('robot_urdf_file must be a non-empty path.')

    output_path = Path(urdf_file)
    if not output_path.parent.is_dir():
        raise FileNotFoundError(f"URDF output directory '{output_path.parent}' does not exist.")

    temporary_path: Path | None = None
    try:
        rendered_urdf = Command(
            _build_xacro_command(xacro_file, xacro_args_file, sim_file)
        ).perform(ctx)
        with NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            prefix=f'.{output_path.name}.',
            suffix='.tmp',
            dir=output_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(rendered_urdf)
            temporary_path = Path(temporary_file.name)
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return [LogInfo(msg=f'Rendered robot URDF: {output_path}')]


def _build_xacro_command(xacro_file: str, xacro_args_file: str, sim_file: str) -> list[Any]:
    """Build the Xacro command with launch-owned runtime and optional YAML arguments."""
    if not xacro_file or not Path(xacro_file).is_file():
        raise FileNotFoundError(f"Xacro file '{xacro_file}' does not exist.")
    if sim_file and not Path(sim_file).is_file():
        raise FileNotFoundError(f"Simulation file '{sim_file}' does not exist.")

    command: list[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        _quote_shell_token(xacro_file),
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
        ' sim_file:=',
        _quote_shell_token(sim_file),
    ]
    for name, value in _load_xacro_args(xacro_args_file).items():
        command.extend([' ', _quote_shell_token(f'{name}:={value}')])
    return command


def _load_xacro_args(path: str) -> dict[str, str]:
    """Load scalar model arguments while reserving runtime arguments for launch."""
    if not path:
        return {}

    resolved_path, values = rlh.read_yaml_file(path)
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise TypeError(f"Xacro arguments file '{resolved_path}' must contain a mapping.")

    result: dict[str, str] = {}
    for name, value in values.items():
        if not isinstance(name, str):
            raise TypeError(f"Xacro arguments file '{resolved_path}' contains a non-string key.")
        if name in ('namespace', 'robot_name', 'sim_file'):
            raise ValueError(f"Xacro arguments file '{resolved_path}' must not set '{name}'.")
        if value is None:
            result[name] = ''
        elif isinstance(value, (bool, int, float, str)):
            result[name] = str(value)
        else:
            raise TypeError(f"Xacro argument '{name}' must be a YAML scalar.")
    return result


def _quote_shell_token(value: str) -> str:
    """Quote one Xacro command token when the shell would reinterpret it."""
    quoted = shlex.quote(value)
    return quoted if quoted != value else value
