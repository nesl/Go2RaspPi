# This is an auto generated Dockerfile for ros:ros-base
# generated from docker_images_ros2/create_ros_image.Dockerfile.em
FROM ros:humble-ros-core-jammy

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-rosdep \
    python3-vcstool \
    && rm -rf /var/lib/apt/lists/*

# bootstrap rosdep
RUN rosdep init && \
  rosdep update --rosdistro $ROS_DISTRO

# setup colcon mixin and metadata
RUN colcon mixin add default \
      https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml && \
    colcon mixin update && \
    colcon metadata add default \
      https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml && \
    colcon metadata update

# install ros2 packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-ros-base=0.10.0-1* \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y bluez bluetooth pip libcairo2-dev libgirepository1.0-dev python-gi-dev nano wget

RUN apt-get install -y python3-pyaudio

RUN pip install bluepy

RUN apt-get install -y cmake gcc build-essential libfftw3-dev libconfig-dev libasound2-dev libpulse-dev libgfortran-*-dev perl

RUN apt-get install -y gfortran texinfo && pip install libconf

RUN git clone https://github.com/introlab/audio_utils.git

WORKDIR audio_utils

RUN git submodule update --init --recursive

SHELL ["/bin/bash", "-c"]

RUN source /opt/ros/humble/setup.bash && colcon build

RUN git clone https://github.com/introlab/odas_ros.git odas_module

WORKDIR odas_module

RUN git submodule update --init --recursive

RUN mv * ../

WORKDIR ..

#RUN source /opt/ros/humble/setup.bash && colcon build

RUN apt-get install -y alsa-utils ros-humble-sensor-msgs-py

#RUN git clone https://github.com/introlab/odas.git

#RUN mv odas/config/odaslive/respeaker_usb_4_mic_array.cfg odas_ros/config/configuration.cfg

#RUN rm -r odas odas_ros/config/configuration.cfg

COPY respeaker_usb_4_mic_array.cfg odas_ros/config/configuration.cfg

RUN sed -i 's/import sensor_msgs\.point_cloud2 as pcl2/from sensor_msgs_py import point_cloud2 as pcl2/' odas_ros/scripts/odas_visualization_node.py

#RUN sed -i 's/card = 1;/card = 3;/' odas_ros/config/configuration.cfg

RUN source /opt/ros/humble/setup.bash && colcon build --packages-select odas_ros_msgs odas_ros


RUN apt-get install -y ffmpeg portaudio19-dev netcat-openbsd

RUN pip install bleak RPi.GPIO mfrc522

COPY docker_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh


#ENV ROS_DOMAIN_ID=78
#WORKDIR /root
#RUN mkdir -p ros2_ws/src
#WORKDIR ros2_ws/src
#RUN source /opt/ros/humble/setup.bash && ros2 pkg create --build-type ament_python --license Apache-2.0 py_pubsub
#WORKDIR py_pubsub/py_pubsub
#RUN wget https://raw.githubusercontent.com/ros2/examples/humble/rclpy/topics/minimal_publisher/examples_rclpy_minimal_publisher/publisher_member_function.py
#RUN wget https://raw.githubusercontent.com/ros2/examples/humble/rclpy/topics/minimal_subscriber/examples_rclpy_minimal_subscriber/subscriber_member_function.py

ENTRYPOINT ["/entrypoint.sh"]
