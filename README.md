# robot_forki3

`robot_forki3` provides digital models of the three-steer Forki3 mobile robot. The package has
two models: `base`, which contains the mobile platform and simple fork, and `a`, which adds the
current camera and lidar sensor layout.

## Resources

### Robot models

The public Xacro files are installed directly under `urdf`:

- `urdf/common.xacro` defines the shared three-steer platform, chassis, wheel geometry, Gazebo
  plugins, and fork interface.
- `urdf/robot_forki3_base.xacro` defines the base model.
- `urdf/robot_forki3_a.xacro` defines model A with the sensor layout.

Each model has its own default configuration directory:

```text
config/model_base/
config/model_a/
```

Each directory contains `default_xacro_args.yaml`, `default_simulation.yaml`,
`default_bridge.yaml`, and `default_params.yaml`. The Xacro arguments configure the model,
simulation configures Gazebo plugins, bridge configures ROS-Gazebo topics, and parameters
configure launched ROS nodes.

### Launch files

The package installs the same reusable launch roles as the common RB-VOGUI package:

- `launch/render_robot_urdf.launch.py` renders an Xacro model into a URDF file.
- `launch/robot_state_publisher.launch.py` reads the rendered URDF and starts the state publisher.
- `launch/bridge.launch.py` starts the ROS-Gazebo bridge.
- `launch/ground_vehicle_kinematics.launch.py` starts the Forki3 three-steer kinematics node.

Render the model first and pass the resulting `robot_urdf_file` to the state publisher.
Only the renderer accepts `robot_xacro_file`, `robot_xacro_args_file`, and `robot_sim_file`.
The debug and simulation launch files share the rendered URDF with the state publisher and Gazebo.

Forki3 also provides `launch/fork_control.launch.py` for its fork controller and two debug launch
files, one for each model:

- `launch/debug_robot_forki3_base.launch.py`
- `launch/debug_robot_forki3_a.launch.py`

## Build

Build from the workspace root:

```bash
colcon build --merge-install --packages-select robot_forki3
source install/setup.bash
```

## Visualize the models

The debug launch files start a simple Gazebo world and RViz. They are intended for inspecting
changes to the models and for checking simulated sensors without starting a complete project.

Both debug models follow the RB-VOGUI startup order: render the URDF, start the world, wait for
Gazebo's create service, and spawn the model from that URDF. A successful spawn starts the state
publisher, bridge, kinematics, fork control, and RViz. A failed readiness check or spawn stops
the launch. `robot_description_topic` selects the state publisher's output topic.

```bash
robot_forki3_share="$(ros2 pkg prefix robot_forki3)/share/robot_forki3"
"${robot_forki3_share}/scripts/debug_robot_forki3_base.sh"
"${robot_forki3_share}/scripts/debug_robot_forki3_a.sh"
```

Pass any launch argument after the script command. To list the available arguments, run:

```bash
ros2 launch robot_forki3 debug_robot_forki3_base.launch.py --show-args
ros2 launch robot_forki3 debug_robot_forki3_a.launch.py --show-args
```

## Tests

Run the package tests from the workspace root:

```bash
colcon build --merge-install --packages-select robot_forki3
colcon test --merge-install --packages-select robot_forki3
colcon test-result --test-result-base build --verbose
```

### Inspect a generated URDF

Render either model and validate its URDF directly:

```bash
robot_forki3_share="$(ros2 pkg prefix robot_forki3)/share/robot_forki3"
ros2 launch robot_forki3 render_robot_urdf.launch.py \
  robot_name:=forki3 \
  robot_xacro_file:="${robot_forki3_share}/urdf/robot_forki3_a.xacro" \
  robot_xacro_args_file:="${robot_forki3_share}/config/model_a/default_xacro_args.yaml" \
  robot_sim_file:="${robot_forki3_share}/config/model_a/default_simulation.yaml" \
  robot_urdf_file:=/tmp/forki3_a.urdf
check_urdf /tmp/forki3_a.urdf
```
