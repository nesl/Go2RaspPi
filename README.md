# Raspberry Pi Audio & Communication Node

This module configures a **Raspberry Pi 4 Model B** as an audio interface and communication bridge between hardware devices and the central server.

## Hardware Requirements

* Raspberry Pi 4 Model B
* ReSpeaker Microphone Array
* External Speaker

## Overview

The Raspberry Pi is responsible for:

* Capturing voice input from the microphone array
* Forwarding raw audio streams to the server
* Receiving raw audio from the server and playing it through the speaker
* Detecting nearby Bluetooth devices and publishing results

## System Components

The system includes the following nodes:

* **Audio Capture**: Captures microphone input and sends raw audio to the server
* **TTS Player (`tts_player`)**: Receives audio data and plays it through the speaker
* **Bluetooth Scanner (`bt_scan_publisher`)**: Detects nearby Bluetooth devices and publishes detections

## Setup Instructions

### 1. Build Docker Container

Navigate to the `docker` directory and build the container:

```bash
cd docker
docker build -t rpi_audio_node .
```

### 2. Run the System

After building the container and cloning this repository inside it, start all required nodes using:

```bash
./start.sh
```

This script will initialize all components, including audio streaming and Bluetooth scanning.

## Notes

* Ensure that the ReSpeaker microphone array and speaker are properly connected before starting the system.
* The system assumes a running server capable of handling raw audio streams.
* Bluetooth functionality depends on the Raspberry Pi’s Bluetooth interface being enabled.

If you want, I can make this consistent with your **other README (simulator + ROS2)** so everything in the repo follows the same style.
