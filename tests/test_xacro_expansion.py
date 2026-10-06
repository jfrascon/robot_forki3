import math
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from conftest import PACKAGE_DIR
from conftest import run_bash

ENABLED_SIMULATION_TOPIC_CASES = (
    ('base', 'base_velocity_controller', ('topic',), 'base_velocity_controller'),
    ('base', 'pose_publisher', ('topic', 'topic_with_covariance', 'tf_topic'), 'pose_publisher'),
    (
        'base',
        'base_steerable_wheel_0_steering_joint_controller',
        ('topic',),
        'base_steerable_wheel_0_steering_joint_controller',
    ),
    (
        'base',
        'base_steerable_wheel_1_steering_joint_controller',
        ('topic',),
        'base_steerable_wheel_1_steering_joint_controller',
    ),
    (
        'base',
        'base_steerable_wheel_2_steering_joint_controller',
        ('topic',),
        'base_steerable_wheel_2_steering_joint_controller',
    ),
    (
        'base',
        'base_steerable_wheel_0_rotation_joint_controller',
        ('topic',),
        'base_steerable_wheel_0_rotation_joint_controller',
    ),
    (
        'base',
        'base_steerable_wheel_1_rotation_joint_controller',
        ('topic',),
        'base_steerable_wheel_1_rotation_joint_controller',
    ),
    (
        'base',
        'base_steerable_wheel_2_rotation_joint_controller',
        ('topic',),
        'base_steerable_wheel_2_rotation_joint_controller',
    ),
    ('base', 'fork_controller', ('topic',), 'fork_controller'),
    ('base', 'joint_state_publisher', ('topic',), 'joint_state_publisher'),
    ('a', 'front_top_lidar', ('base_topic',), 'livox_mid360'),
    ('a', 'front_top_lidar_imu', ('topic',), 'livox_mid360'),
    ('a', 'back_bottom_lidar', ('topic',), 'sick_mics3_cbaz40pz1'),
    ('a', 'joint_state_publisher', ('topic',), 'joint_state_publisher'),
)


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_xacro_expands_to_valid_urdf(robot_model: str, tmp_path: Path) -> None:
    urdf_path = tmp_path / f'{robot_model}.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'

    result = run_bash(f'xacro "{xacro_path}" > "{urdf_path}" && check_urdf "{urdf_path}"')

    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert urdf_path.is_file(), output
    assert 'Successfully Parsed XML' in output, output


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_simulation_xacro_expands_to_valid_urdf(robot_model: str, tmp_path: Path) -> None:
    urdf_path = tmp_path / f'{robot_model}_simulation.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'
    sim_path = PACKAGE_DIR / 'config' / f'model_{robot_model}' / 'default_simulation.yaml'

    result = run_bash(
        f'xacro "{xacro_path}" sim_file:="{sim_path}" > "{urdf_path}" && check_urdf "{urdf_path}"'
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert 'Successfully Parsed XML' in output, output
    assert 'gz::sim::systems::OdometryPublisher' in urdf_path.read_text(encoding='utf-8')


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_whitespace_only_sim_file_builds_real_description(
    robot_model: str, tmp_path: Path
) -> None:
    urdf_path = tmp_path / f'{robot_model}_whitespace_sim_file.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'

    result = run_bash(
        f'xacro "{xacro_path}" sim_file:="   " > "{urdf_path}" && check_urdf "{urdf_path}"'
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert '<plugin ' not in urdf_path.read_text(encoding='utf-8')


@pytest.mark.parametrize(
    ('argument', 'element'), [('body_use_visual', 'visual'), ('body_use_collision', 'collision')]
)
def test_body_geometry_can_be_disabled(argument: str, element: str, tmp_path: Path) -> None:
    urdf_path = tmp_path / f'{argument}.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_base.xacro'

    result = run_bash(
        f'xacro "{xacro_path}" {argument}:=False > "{urdf_path}" && check_urdf "{urdf_path}"'
    )

    assert result.returncode == 0, result.stdout + result.stderr
    base_link = ElementTree.parse(urdf_path).find("./link[@name='forki3_base_link']")
    assert base_link is not None
    assert base_link.find(element) is None


@pytest.mark.parametrize(
    ('argument', 'wheel_name'),
    [
        ('s_wheel_front_use_visual', 'steerable_wheel_0'),
        ('s_wheel_left_use_visual', 'steerable_wheel_1'),
        ('s_wheel_right_use_visual', 'steerable_wheel_2'),
    ],
)
def test_wheel_visual_can_be_disabled(argument: str, wheel_name: str, tmp_path: Path) -> None:
    urdf_path = tmp_path / f'{argument}.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_base.xacro'

    result = run_bash(
        f'xacro "{xacro_path}" {argument}:=False > "{urdf_path}" && check_urdf "{urdf_path}"'
    )

    assert result.returncode == 0, result.stdout + result.stderr
    wheel_link = ElementTree.parse(urdf_path).find(
        f"./link[@name='forki3_{wheel_name}_rotation_link']"
    )
    assert wheel_link is not None
    assert wheel_link.find('visual') is None
    assert wheel_link.find('collision') is not None


@pytest.mark.parametrize(
    'mount_argument, expected_pitch',
    [('', math.pi / 6), ('front_top_lidar_mount:="-0.07647355 0 1.786 0 0 0"', 0.0)],
    ids=['tilted_default', 'level_override'],
)
def test_model_a_mounts_one_livox_mid360_on_the_base_link(
    tmp_path: Path, mount_argument: str, expected_pitch: float
) -> None:
    urdf_path = tmp_path / 'model_a.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_a.xacro'

    result = run_bash(f'xacro "{xacro_path}" {mount_argument} > "{urdf_path}"')

    assert result.returncode == 0, result.stdout + result.stderr
    robot = ElementTree.parse(urdf_path)
    lidar_joint = robot.find("./joint[@name='forki3_front_top_lidar_root_joint']")
    assert lidar_joint is not None
    assert lidar_joint.find("parent[@link='forki3_base_link']") is not None
    assert lidar_joint.find("child[@link='forki3_front_top_lidar_root_link']") is not None
    origin = lidar_joint.find('origin')
    assert origin is not None
    assert origin.attrib['xyz'] == '-0.07647355 0 1.786'
    assert tuple(float(value) for value in origin.attrib['rpy'].split()) == pytest.approx(
        (0.0, expected_pitch, 0.0)
    )
    assert robot.find("./link[@name='forki3_back_top_lidar_root_link']") is None
    assert robot.find("./link[@name='forki3_top_platform_link']") is None
    assert not [
        link
        for link in robot.findall('link')
        if link.attrib['name'].startswith('forki3_fork_camera')
    ]


def test_model_a_mounts_microscan3_on_the_base_link(tmp_path: Path) -> None:
    urdf_path = tmp_path / 'model_a.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_a.xacro'

    result = run_bash(f'xacro "{xacro_path}" > "{urdf_path}"')

    assert result.returncode == 0, result.stdout + result.stderr
    robot = ElementTree.parse(urdf_path)
    lidar_joint = robot.find("./joint[@name='forki3_back_bottom_lidar_root_joint']")
    assert lidar_joint is not None
    assert lidar_joint.find("parent[@link='forki3_base_link']") is not None
    assert lidar_joint.find("child[@link='forki3_back_bottom_lidar_root_link']") is not None
    origin = lidar_joint.find('origin')
    assert origin is not None
    assert tuple(float(value) for value in origin.attrib['xyz'].split()) == pytest.approx(
        (-0.692435, 0.0, 0.019941)
    )
    assert tuple(float(value) for value in origin.attrib['rpy'].split()) == pytest.approx(
        (0.0, 0.0, math.pi)
    )


def test_model_a_livox_ring_approximation_matches_mid360_specs() -> None:
    simulation_path = PACKAGE_DIR / 'config' / 'model_a' / 'default_simulation.yaml'
    simulation_config = yaml.safe_load(simulation_path.read_text(encoding='utf-8'))
    lidar_config = simulation_config['front_top_lidar']

    assert lidar_config['update_rate'] == 10.0
    assert lidar_config['hor_fov_deg'] == {'min_angle': -180, 'max_angle': 180}
    assert lidar_config['ver_fov_deg'] == {'min_angle': -7, 'max_angle': 52}
    assert lidar_config['hor_res_deg'] == 0.2
    assert lidar_config['ver_res_deg'] == 5.9
    assert lidar_config['dist_span'] == {'min_dist': 0.1, 'max_dist': 70}
    assert lidar_config['gaussian_noise'] == {'mean': 0, 'stddev': 0.02}


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_three_swerve_parameters_match_generated_wheel_geometry(
    robot_model: str, tmp_path: Path
) -> None:
    """Keep kinematic wheel positions synchronized with the generated Forki3 URDF."""
    urdf_path = tmp_path / f'{robot_model}_wheel_geometry.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'
    params_path = PACKAGE_DIR / 'config' / f'model_{robot_model}' / 'default_params.yaml'

    result = run_bash(f'xacro "{xacro_path}" > "{urdf_path}"')
    assert result.returncode == 0, result.stdout + result.stderr

    robot = ElementTree.parse(urdf_path)
    params = yaml.safe_load(params_path.read_text(encoding='utf-8'))
    wheels = params['/**/three_swerve_kinematics']['ros__parameters']['steerable_wheels']

    for wheel_index in range(3):
        wheel_name = f'steerable_wheel_{wheel_index}'
        wheel_params = wheels[wheel_name]
        steering_joint = robot.find(f"./joint[@name='forki3_{wheel_name}_steering_joint']")
        rotation_link = robot.find(f"./link[@name='forki3_{wheel_name}_rotation_link']")

        assert steering_joint is not None
        assert rotation_link is not None
        origin = steering_joint.find('origin')
        collision_cylinder = rotation_link.find('./collision/geometry/cylinder')
        assert origin is not None
        assert collision_cylinder is not None

        x, y, _ = (float(value) for value in origin.attrib['xyz'].split())
        expected_alpha = math.atan2(y, x)
        expected_dist = math.hypot(x, y)

        assert wheel_params['radius'] == pytest.approx(
            float(collision_cylinder.attrib['radius']), abs=1e-12
        )
        assert wheel_params['dist'] == pytest.approx(expected_dist, abs=1e-12)
        assert wheel_params['alpha'] == pytest.approx(expected_alpha, abs=1e-12)
        assert wheel_params['beta'] == pytest.approx(math.pi / 2.0 - expected_alpha, abs=1e-12)
        assert wheel_params['name'] == f'$(var robot_prefix){wheel_name}'
        assert wheel_params['steering_joint']['name'] == (
            f'$(var robot_prefix){wheel_name}_steering_joint'
        )
        assert wheel_params['rotation_joint']['name'] == (
            f'$(var robot_prefix){wheel_name}_rotation_joint'
        )


@pytest.mark.parametrize('robot_model', ['base', 'a'])
def test_nonexistent_sim_file_is_rejected(robot_model: str, tmp_path: Path) -> None:
    missing_sim_path = tmp_path / 'missing_simulation.yaml'
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'

    result = run_bash(f'xacro "{xacro_path}" sim_file:="{missing_sim_path}"')
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert str(missing_sim_path) in output


@pytest.mark.parametrize(
    ('robot_model', 'component_name', 'topic_keys', 'expected_error'),
    ENABLED_SIMULATION_TOPIC_CASES,
)
def test_enabled_simulation_component_requires_a_topic(
    robot_model: str,
    component_name: str,
    topic_keys: tuple[str, ...],
    expected_error: str,
    tmp_path: Path,
) -> None:
    source_path = PACKAGE_DIR / 'config' / f'model_{robot_model}' / 'default_simulation.yaml'
    simulation_config = yaml.safe_load(source_path.read_text(encoding='utf-8'))

    assert simulation_config[component_name]['enabled'] is True
    for topic_key in topic_keys:
        simulation_config[component_name][topic_key] = ''

    invalid_sim_path = tmp_path / f'{component_name}.yaml'
    invalid_sim_path.write_text(yaml.safe_dump(simulation_config), encoding='utf-8')
    xacro_path = PACKAGE_DIR / 'urdf' / f'robot_forki3_{robot_model}.xacro'

    result = run_bash(f'xacro "{xacro_path}" sim_file:="{invalid_sim_path}"')
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert expected_error in output


def test_disabled_simulation_component_allows_an_empty_topic(tmp_path: Path) -> None:
    source_path = PACKAGE_DIR / 'config' / 'model_base' / 'default_simulation.yaml'
    simulation_config = yaml.safe_load(source_path.read_text(encoding='utf-8'))
    simulation_config['base_velocity_controller'].update(enabled=False, topic='')

    sim_path = tmp_path / 'disabled_base_velocity_controller.yaml'
    sim_path.write_text(yaml.safe_dump(simulation_config), encoding='utf-8')
    xacro_path = PACKAGE_DIR / 'urdf' / 'robot_forki3_base.xacro'

    result = run_bash(f'xacro "{xacro_path}" sim_file:="{sim_path}"')

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    'launch_file', ['debug_robot_forki3_base.launch.py', 'debug_robot_forki3_a.launch.py']
)
def test_launch_show_args_lists_file_based_model_arguments(launch_file: str) -> None:
    result = run_bash(f'ros2 launch robot_forki3 {launch_file} --show-args')
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "'robot_name'" in output, output
    assert "'robot_params_file'" in output, output
    assert "'robot_params_file_allow_substs'" in output, output
    assert "'robot_xacro_args_file'" in output, output

    if launch_file.startswith('debug_'):
        assert "'robot_sim_file'" in output, output
        assert "'robot_bridge_config_file'" in output, output
