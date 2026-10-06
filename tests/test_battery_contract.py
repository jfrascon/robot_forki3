import yaml

from conftest import PACKAGE_DIR


def test_default_simulation_enables_the_battery_for_both_models() -> None:
    """Require both Forki3 models to publish an ideal simulated battery state."""
    expected = {
        'enabled': True,
        'voltage': 24.0,
        'capacity': 20.0,
        'power_load': 0.0,
        'fix_issue_225': True,
    }

    for model_name in ('base', 'a'):
        config_path = PACKAGE_DIR / 'config' / f'model_{model_name}' / 'default_simulation.yaml'
        simulation = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        assert simulation['battery'] == expected


def test_common_xacro_and_bridge_define_the_battery_contract() -> None:
    """Require the battery plugin and its dynamically named ROS bridge entry."""
    common_source = (PACKAGE_DIR / 'urdf' / 'common.xacro').read_text(encoding='utf-8')
    bridge_source = (PACKAGE_DIR / 'launch' / 'bridge.launch.py').read_text(encoding='utf-8')

    assert '<xacro:plugin_linear_battery' in common_source
    assert 'name="main_battery"' in common_source
    assert 'create_battery_bridges(' in bridge_source
    assert "battery_state_ros_topic='main_battery/state'" in bridge_source
