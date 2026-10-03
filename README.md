## About This Project

This repository is a fork of our undergraduate capstone project at  
Tamkang University, Department of Computer Science and Information Engineering.

**Project:** VoI-Driven Transport Selection for Heterogeneous LoRa/Wi-Fi IoT with Unified MQTT Abstraction

### My Contributions

My primary contributions focused on:

- Water-level data preprocessing and semantic state design
- Four-state water-level inference: Stable, Rising, Flood, and Receding
- Teacher model and lightweight student model development
- Edge AI model integration and deployment-related work
- Integration of semantic inference with the adaptive transmission decision pipeline

**Original Team Repository:**  
https://github.com/HungPage/VoI-Driven-Transport-Selection-for-Heterogeneous-LoRa-Wi-Fi-IoT-with-Unified-MQTT-Abstraction
# VoI-Driven Adaptive Transport for Heterogeneous LoRa/Wi-Fi Flood Monitoring

Semantic-aware water level monitoring using on-device AI and adaptive LoRa/Wi-Fi transport selection on Raspberry Pi Pico 2W (264 KB SRAM).

---

# Overview

Urban underground culverts suffer from:

- Poor wireless signal penetration
- Limited power supply
- Packet loss during flooding
- Difficult deployment environments

Traditional communication approaches are insufficient:

| Strategy | Problem |
|---|---|
| Always-WiFi | Fast but drains batteries quickly |
| Always-LoRa | Energy-efficient but high latency |
| Periodic switching | Event-blind and unreliable |
| RSSI-only routing | Lacks semantic understanding |

This project introduces a **Value of Information (VoI) driven adaptive transport framework** for heterogeneous LoRa/WiFi IoT flood monitoring systems.

Instead of selecting communication links purely based on signal strength or periodic schedules, the system allows the **semantic urgency of water level data** to determine:

- Which radio interface to use
- Whether acknowledgments are required
- Whether retransmission is necessary
- Whether relay routing should be enabled

The system runs entirely on:

- Raspberry Pi Pico 2W
- MicroPython
- 264 KB SRAM
- No external ML framework

---

# Key Features

## Semantic-Aware Edge AI

A lightweight on-device decision tree classifies water levels into:

- S0 — Stable
- S1 — Rising
- S2 — Flood Peak
- S3 — Receding

Model performance:

| Metric | Value |
|---|---|
| Model Size | 3.1 KB |
| Inference Latency | 79 μs |
| Platform | Raspberry Pi Pico 2W |
| Macro F1 | 0.8588 |

---

## Adaptive LoRa/WiFi Switching

Each semantic state maps to a dedicated communication strategy:

| State | Link Class | Transport |
|---|---|---|
| S0 | B | LoRa-1× |
| S1 | C | WiFi ECO |
| S2 | A | WiFi STD |
| S3 | D | LoRa-2× |

This enables:

- Low energy consumption during stable periods
- High reliability during floods
- Automatic transport escalation

---

## Bidirectional Fallback

If a communication interface fails:

- Automatic fallback activates after 3 failures
- Pending packets are queued
- Recovery probing restores the original path

Supported fallback directions:

- LoRa → WiFi
- WiFi → LoRa

---

## AODV Multi-Hop Routing

For deep underground culverts:

- AODV maintains routes dynamically
- Maximum hop count = 3
- Relay nodes extend LoRa coverage

Supported packet types:

- HELLO
- RREQ
- RREP
- RERR
- ROUTE
- QHINT

---

## On-Device DQN Relay Advisor

A lightweight DQN model advises whether packets should:

- Use direct transmission
- Use relay forwarding

Neural network structure:

```text
Input (6)
   ↓
Hidden Layer (12 ReLU)
   ↓
Output (2 Q-values)
```

Hybrid routing decision:

```text
Final Decision =
0.25 × DQN output +
0.75 × RSSI heuristic
```

---

## Unified MQTT Abstraction

Both LoRa and WiFi packets are converted into identical JSON payloads:

```json
{
  "node_id": 3,
  "water_level": 7.23,
  "voi_state": "S1",
  "link_class": "C",
  "transport": "LORA",
  "rssi": -78,
  "hop_count": 1,
  "seq": 124,
  "ts": 1712345678,
  "exp_label": "VOI_DRIVEN"
}
```

Upper-layer tools become completely channel-transparent:

- Dashboard
- CSV logger
- Energy analyzer
- MQTT subscribers

MQTT topic format:

```text
sensor/node_{id}/data
```

---

# System Architecture

```text
[Leaf Nodes: Pico 2W + RYLR998]
        │
        ├── LoRa (923 MHz)
        └── WiFi (TCP)
                │
                ▼
        [Sink Gateway]
                │
        ┌───────┼────────┐
        │       │        │
        ▼       ▼        ▼
    MQTT     CSV      Dashboard
    Broker   Logger   WebSocket UI
```

---

# Internal Processing Pipeline

## Leaf Node Pipeline

```text
Water Level Reading
        ↓
Feature Extraction
        ↓
Decision Tree Inference
        ↓
VoI State Classification
        ↓
VoI → Link Mapping
        ↓
Fallback Override
        ↓
AODV / DQN Relay Decision
        ↓
Transmission
```

---

## Sink Gateway Pipeline

```text
LoRa Polling + WiFi Polling
            ↓
Packet Parsing
            ↓
JSON Normalization
            ↓
MQTT Publishing
            ↓
Dashboard / Logger / Analytics
```

---

# Semantic End — Edge AI & VoI

## Four Semantic States

| State | Meaning | Behaviour |
|---|---|---|
| S0 | Stable | LoRa-1× heartbeat |
| S1 | Rising | WiFi ECO |
| S2 | Flood Peak | WiFi STD + ACK |
| S3 | Receding | LoRa-2× redundancy |

---

## Debounce Protection

To avoid unstable switching:

- State transition requires 3 consecutive identical states
- Emergency bypass forces S2 immediately if:

```text
water_level ≥ ALERT_LINE + 0.2 m
```

---

# Teacher-Student Compression

Because Pico 2W has limited SRAM, a high-accuracy CatBoost teacher model is compressed into a tiny decision tree.

## Teacher Model

- CatBoost
- Trained on 2,878 real flood records
- Macro F1 = 0.9001

## Student Model

- Depth-3 decision tree
- Frozen into if-else rules
- Macro F1 = 0.8588

Per-class recall:

| State | Recall |
|---|---|
| S0 | 1.000 |
| S1 | 0.936 |
| S2 | 0.544 |
| S3 | 0.893 |

---

# VoI-to-Link Hard Rules

| VoI | Link Class | Interface | ACK | Energy |
|---|---|---|---|---|
| S0 | B | LoRa | No | 100 mJ |
| S1 | C | WiFi ECO | No | 400 mJ |
| S2 | A | WiFi STD | Yes | 600 mJ |
| S3 | D | LoRa-2× | Double TX | 200 mJ |

Energy model:

```text
E_packet =
E_base(link_class) × hop_count +
P_idle × Δt
```

Where:

```text
P_idle = 38.5 mW
```

---

# Network End — Heterogeneous Transport

## Dual Radio Configuration

| Radio | Configuration |
|---|---|
| LoRa | 923 MHz, SF10, BW125kHz |
| WiFi | TCP Socket, Port 5000 |

---

## LoRa Features

- Software ACK
- UART health monitoring
- Automatic reset after repeated failures

---

## WiFi Features

- Static IP
- RSSI monitoring
- Automatic reconnect
- LoRa-only degradation mode

---

# Bidirectional Fallback

Fallback activates after:

```text
3 consecutive transmission failures
```

## Pending Queue

During fallback:

- Packets are NOT dropped
- Packets enter pending queue
- Retransmission occurs automatically

---

# AODV + DQN Hybrid Routing

## DQN State Vector

```python
[
    rssi_norm,
    hops_norm,
    risk,
    success_rate,
    epsilon,
    voi_urgency
]
```

## Reward Function

| Event | Reward |
|---|---|
| Direct success | +1.0 |
| Relay success | +0.6 |
| Failure | -1.0 |

---

# Hardware Requirements

| Component | Quantity |
|---|---|
| Raspberry Pi Pico 2W | ≥2 |
| RYLR998 LoRa Module | 1 per node |
| Water Level Sensor | 1 |
| Power Supply | As needed |
| Laptop / PC | 1 |

---

# Wiring

```text
RYLR998 → Pico 2W

VCC → 3.3V
GND → GND
TX  → GP5
RX  → GP4
```

---

# Quick Start

## 1. Install Dependencies

### Linux

```bash
sudo apt install mosquitto mosquitto-clients
```

### macOS

```bash
brew install mosquitto
brew services start mosquitto
```

### Python Packages

```bash
pip install paho-mqtt matplotlib numpy
```

---

## 2. Flash Firmware

Upload:

```text
firmware/leaf_main.py
firmware/sink_main.py
```

Configure:

- NODE_ID
- WiFi SSID
- Password
- Sink IP

---

## 3. Start MQTT CSV Logger

```bash
python tools/mqtt_csv_logger.py \
    --broker 127.0.0.1 \
    --out ./experiments
```

---

## 4. Replay Flood Dataset

```bash
python tools/csv_replay.py \
    --serial /dev/ttyACM0 \
    --csv data/.csv
```

---

## 5. Launch Dashboard

```bash
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

---

# Experimental Results

## Hardware Experiment

Real Pico 2W deployment using replayed Bridge flood data.

| Strategy | Avg Power | Reachability | Battery Life |
|---|---|---|---|
| Always-WiFi | 169.73 mW | 5/5 | 6.0 days |
| VoI-Driven | 131.07 mW | 5/5 | 7.3 days |
| RSSI-Based | 118.32 mW | 4/5 | 8.0 days |
| Periodic | 74.13 mW | 4/5 | 12.8 days |
| Always-LoRa | 62.41 mW | 5/5 | 15.2 days |

---

## Key Findings

- VoI-Driven reduces energy consumption by 22.8%
- Maintains perfect reachability
- Only strategy using all four link classes
- Periodic switching misses critical alerts
- Always-LoRa suffers excessive S2 latency

---

## Simulation Results

| Strategy | S2 Delivery Rate | Energy |
|---|---|---|
| VoI-Driven | 82.5% | 562 J |
| Always-WiFi | 80.5% | 1203 J |
| Always-LoRa | 59.0% | 199.7 J |

---

# Known Limitations

## Critical Issue

S2 recall:

```text
0.5441
```

Approximately 45.6% of flood peaks are misclassified.

This may downgrade:

```text
WiFi STD → LoRa-2×
```

leading to higher latency.

---

## Additional Limitations

- Energy values are model-based
- DQN benefit not fully isolated
- CSV logs only successful packets
- Current deployment scale ≤5 nodes

---

# Future Work

- Real bridge deployment
- Interrupt-driven low-power sensing
- Larger-scale DQN evaluation
- INA219 real current measurement
- Landslide/debris monitoring extension
- Online model adaptation

---

# Repository Structure

```text
.
├── firmware/
│   ├── leaf_main.py
│   ├── sink_main.py
│   └── native_decision_tree.mpy
│
├── tools/
│   ├── mqtt_csv_logger.py
│   ├── compute_energy.py
│   ├── csv_replay.py
│   └── simulation/
│
├── dashboard/
│   └── index.html
│
├── data/
│   └──###
│
├── docs/
│   └── full_report.pdf
│
└── README.md
```

---

# Live Dashboard

Demo:

https://hungpage.github.io

Dashboard features:

- Real-time VoI states
- Link class monitoring
- RSSI visualization
- AODV topology map
- DQN routing intent
- Energy statistics
- Fallback monitoring

---

# Dataset

Dataset source:

- October 2022
- Minute-level water level records
- 2,878 samples

Provided by:

- Hydraulic Engineering Office
- Taipei City Government

---


Department of Computer Science and Information Engineering  
Tamkang University  
New Taipei, Taiwan

---

# GitHub Repository

https://github.com/HungPage/VoI-Driven-Transport-Selection-for-Heterogeneous-LoRa-Wi-Fi-IoT-with-Unified-MQTT-Abstraction

---


# Citation

```bibtex
@misc{voi_driven_flood_monitoring_2026,
  title={VoI-Driven Adaptive Transport for Heterogeneous LoRa/WiFi Flood Monitoring},
  author={Hong, Jun-Sen and Weng, Zi-Xiang and Lai, Si-Yuan},
  year={2026},
  institution={Tamkang University},
  note={MicroPython-based semantic-aware flood monitoring system}
}
```

---

# Acknowledgments

- Hydraulic Engineering Office, Taipei City Government
- Raspberry Pi Pico 2W
- REYAX RYLR998
---
