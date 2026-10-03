import argparse
import csv
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("[ERROR] pip3 install paho-mqtt")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# CSV 欄位定義
# ─────────────────────────────────────────────────────────────
PACKET_HEADERS = [
    "timestamp", "dev_id", "seq",
    "state", "voi_state", "water_level_m", "delta_10m", "risk",
    "transport", "link_class", "target_lc", "actual_lc", "is_fallback",
    "rssi", "orig_rssi",
    "hop_count", "via_relay", "relay_path",
    "energy_mj", "reward", "success_rate",
]

FALLBACK_HEADERS = [
    "timestamp", "node", "in_fb", "enter_count", "recover_count",
    "pending_now", "resent_total",
]

AODV_HEADERS = [
    "timestamp", "event_type", "node", "next_hop", "hops", "rssi", "info",
]

ENERGY_HEADERS = [
    "timestamp", "node", "cumulative_mj", "packets_by_lc",
]


# ─────────────────────────────────────────────────────────────
# Logger state
# ─────────────────────────────────────────────────────────────
class ExperimentLogger:
    def __init__(self, out_dir: Path, broker: str, port: int = 1883):
        self.out_dir = out_dir
        self.broker = broker
        self.port = port
        # 目前活躍 experiment dir (按 exp_label 分)
        self.active_exps = {}  # label → dir path
        # 每個 experiment 的 CSV writers (lazy open)
        self.writers = {}  # (label, kind) → (file, csv_writer)
        # 每個 experiment 的 summary 統計
        self.summaries = {}  # label → dict
        # 未知 label 的封包仍要記錄,歸到 "_default"
        self.default_label = "_default"

        self.client = mqtt.Client(
            client_id=f"csv_logger_{int(time.time())}",
            protocol=mqtt.MQTTv311,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.start_ts = datetime.now().isoformat()

    # ─────────────────────────────────────────────
    # MQTT callbacks
    # ─────────────────────────────────────────────
    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[MQTT] connect failed rc={rc}")
            return
        print(f"[MQTT] connected to {self.broker}:{self.port}")
        # 訂閱所有相關 topic
# 修正後的程式碼片段
        topics = [
            ("sensor/+/data", 0),          # 修正：直接用 + 代表節點 ID 層級
            ("sensor/+/hop_info", 0),      # 修正
            ("sensor/+/heartbeat", 0),     # 修正
            ("sensor/sink/energy", 0),
            ("sensor/sink/fallback_stats", 0),
            ("sensor/sink/aodv_event", 0),
            ("sensor/sink/ready", 0),
        ]
        for t, q in topics:
            client.subscribe(t, q)
        print(f"[MQTT] subscribed {len(topics)} topics")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[parse] {msg.topic}: {e}")
            return
        topic = msg.topic

        # 分派到對應處理函式
        try:
            if topic.endswith("/data"):
                self._handle_data(payload)
            elif topic == "sensor/sink/energy":
                self._handle_energy(payload)
            elif topic == "sensor/sink/fallback_stats":
                self._handle_fallback(payload)
            elif topic == "sensor/sink/aodv_event":
                self._handle_aodv(payload)
            elif topic == "sensor/sink/ready":
                print(f"[SINK] ready: {payload}")
        except Exception as e:
            print(f"[handle] topic={topic} err={e}")

    # ─────────────────────────────────────────────
    # Per-topic handlers
    # ─────────────────────────────────────────────
    def _handle_data(self, pkt):
        label = pkt.get("exp_label") or self.default_label
        dev_id = pkt.get("dev_id", "node_??")
        self._ensure_experiment(label)

        # 寫 per-node packets CSV
        node_csv = f"{dev_id}_packets.csv"
        w = self._get_writer(label, node_csv, PACKET_HEADERS)
        rp = pkt.get("relay_path", [])
        w.writerow({
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "dev_id": dev_id,
            "seq": pkt.get("seq"),
            "state": pkt.get("state"),
            "voi_state": pkt.get("voi_state"),
            "water_level_m": pkt.get("water_level_m"),
            "delta_10m": pkt.get("delta_10m"),
            "risk": pkt.get("risk"),
            "transport": pkt.get("transport"),
            "link_class": pkt.get("link_class"),
            "target_lc": pkt.get("target_lc"),
            "actual_lc": pkt.get("actual_lc"),
            "is_fallback": pkt.get("is_fallback"),
            "rssi": pkt.get("rssi"),
            "orig_rssi": pkt.get("orig_rssi"),
            "hop_count": pkt.get("hop_count"),
            "via_relay": pkt.get("via_relay"),
            "relay_path": "|".join(str(x) for x in rp) if rp else "",
            "energy_mj": pkt.get("energy_mj"),
            "reward": pkt.get("reward"),
            "success_rate": pkt.get("success_rate"),
        })
        # flush periodically so data not lost on ctrl-c
        self._flush_if_due(label, node_csv)

        # 更新即時 summary
        s = self.summaries[label]
        s["packets"] += 1
        lc = pkt.get("link_class", "?")
        s["lc_counts"][lc] = s["lc_counts"].get(lc, 0) + 1
        state = pkt.get("state", "?")
        s["state_counts"][state] = s["state_counts"].get(state, 0) + 1
        if pkt.get("is_fallback"):
            s["fb_packets"] += 1
        if pkt.get("hop_count", 1) > 1:
            s["multi_hop_packets"] += 1
        s["energy_mj_total"] += float(pkt.get("energy_mj") or 0.0)
        s["nodes_seen"].add(dev_id)

        # 每 50 筆印一次進度,避免 log 太安靜
        if s["packets"] % 50 == 0:
            print(f"[{label}] pkts={s['packets']} "
                  f"nodes={len(s['nodes_seen'])} "
                  f"fb={s['fb_packets']} "
                  f"multi_hop={s['multi_hop_packets']} "
                  f"e_mJ={s['energy_mj_total']:.0f}")

    def _handle_energy(self, payload):
        # sink 的 per-node 累積能耗
        for label in self.active_exps:
            w = self._get_writer(label, "energy_timeseries.csv", ENERGY_HEADERS)
            for node_key, val in payload.items():
                if not node_key.startswith("node_"):
                    continue
                w.writerow({
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "node": node_key,
                    "cumulative_mj": val if isinstance(val, (int, float)) else None,
                    "packets_by_lc": json.dumps({}),
                })
            self._flush_if_due(label, "energy_timeseries.csv")

    def _handle_fallback(self, payload):
        for label in self.active_exps:
            w = self._get_writer(label, "fallback_events.csv", FALLBACK_HEADERS)
            for node_key, stats in payload.items():
                if not node_key.startswith("node_"):
                    continue
                if not isinstance(stats, dict):
                    continue
                w.writerow({
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "node": node_key,
                    "in_fb": stats.get("in_fb", 0),
                    "enter_count": stats.get("enter_count", 0),
                    "recover_count": stats.get("recover_count", 0),
                    "pending_now": stats.get("pending_now", 0),
                    "resent_total": stats.get("resent_total", 0),
                })
            self._flush_if_due(label, "fallback_events.csv")

    def _handle_aodv(self, payload):
        for label in self.active_exps:
            w = self._get_writer(label, "aodv_events.csv", AODV_HEADERS)
            w.writerow({
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "event_type": payload.get("type", "?"),
                "node": payload.get("node") or payload.get("src"),
                "next_hop": payload.get("nh") or payload.get("next_hop"),
                "hops": payload.get("hops"),
                "rssi": payload.get("rssi"),
                "info": json.dumps({k: v for k, v in payload.items()
                                    if k not in ("type", "node", "nh", "hops", "rssi")}),
            })
            self._flush_if_due(label, "aodv_events.csv")

    # ─────────────────────────────────────────────
    # Experiment dir / writer lifecycle
    # ─────────────────────────────────────────────
    def _ensure_experiment(self, label: str):
        if label in self.active_exps:
            return
        exp_dir = self.out_dir / label
        exp_dir.mkdir(parents=True, exist_ok=True)
        self.active_exps[label] = exp_dir

        # 寫 config.json
        config_path = exp_dir / "config.json"
        if not config_path.exists():
            config_path.write_text(json.dumps({
                "exp_label": label,
                "logger_started": self.start_ts,
                "broker": f"{self.broker}:{self.port}",
            }, indent=2, ensure_ascii=False))

        # 初始化 summary
        self.summaries[label] = {
            "packets": 0,
            "lc_counts": {},
            "state_counts": {},
            "fb_packets": 0,
            "multi_hop_packets": 0,
            "energy_mj_total": 0.0,
            "nodes_seen": set(),
            "first_pkt": datetime.now().isoformat(),
        }
        print(f"[EXP] new label={label} dir={exp_dir}")

    def _get_writer(self, label: str, filename: str, headers: list):
        key = (label, filename)
        if key in self.writers:
            return self.writers[key][1]
        path = self.active_exps[label] / filename
        is_new = not path.exists()
        f = open(path, "a", newline="", encoding="utf-8")
        w = csv.DictWriter(f, fieldnames=headers)
        if is_new:
            w.writeheader()
            f.flush()
        self.writers[key] = (f, w, 0)   # 0 = write count since last flush
        return w

    def _flush_if_due(self, label: str, filename: str):
        key = (label, filename)
        if key not in self.writers:
            return
        f, w, cnt = self.writers[key]
        cnt += 1
        if cnt >= 10:   # 每 10 筆 flush 一次
            f.flush()
            cnt = 0
        self.writers[key] = (f, w, cnt)

    # ─────────────────────────────────────────────
    # Summary writing
    # ─────────────────────────────────────────────
    def write_summaries(self):
        """所有 experiment 的 summary 寫出到對應資料夾"""
        for label, s in self.summaries.items():
            path = self.active_exps[label] / "summary.json"
            path.write_text(json.dumps({
                "exp_label": label,
                "logger_started": self.start_ts,
                "logger_stopped": datetime.now().isoformat(),
                "packets_total": s["packets"],
                "packets_by_lc": s["lc_counts"],
                "packets_by_state": s["state_counts"],
                "packets_fallback": s["fb_packets"],
                "packets_multi_hop": s["multi_hop_packets"],
                "estimated_total_energy_mj": round(s["energy_mj_total"], 2),
                "nodes_seen": sorted(s["nodes_seen"]),
                "first_packet": s.get("first_pkt"),
            }, indent=2, ensure_ascii=False))
            print(f"[SUMMARY] {label}: {s['packets']} pkts, "
                  f"{s['energy_mj_total']:.0f} mJ, "
                  f"nodes={sorted(s['nodes_seen'])}")

    # ─────────────────────────────────────────────
    # Run loop
    # ─────────────────────────────────────────────
    def run(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
        except Exception as e:
            print(f"[MQTT] connect failed: {e}")
            sys.exit(2)
        self.client.loop_forever()

    def close(self):
        print("\n[logger] closing...")
        self.client.disconnect()
        for (f, w, _) in self.writers.values():
            try:
                f.flush(); f.close()
            except Exception:
                pass
        self.write_summaries()
        print("[logger] done")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="GCCE experiment CSV logger")
    p.add_argument("--broker", default="127.0.0.1",
                   help="MQTT broker IP (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--out", default="./experiments",
                   help="output root directory (default: ./experiments)")
    args = p.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[logger] output → {out_dir}")

    logger = ExperimentLogger(out_dir, args.broker, args.port)

    def _sigint(signum, frame):
        logger.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)
    logger.run()


if __name__ == "__main__":
    main()
