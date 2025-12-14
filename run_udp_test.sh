#!/bin/bash

# ===== CONFIG =====
PCAP_FILE="/mnt/d/Github/Network-Project/udp_test_capture.pcap"
TEST_DURATION=60   # default duration in seconds
INTERFACE="lo"     # network interface (adjust if needed)


# ======== LOG ========
LOG_FILE="/mnt/d/Github/Network-Project/test_run_$(date +%Y%m%d_%H%M%S).txt"

exec > >(tee -a "$LOG_FILE") 2>&1

# ===== SCENARIO SELECTION =====
echo "Select test scenario:"
echo "1) Baseline (no impairment)"
echo "2) Loss 5%"
echo "3) Delay + Jitter (100ms ±10ms)"
read -p "Enter choice [1-3]: " SCENARIO

# ===== CLEANUP =====
# Remove existing qdisc safely
sudo tc qdisc del dev $INTERFACE root 2>/dev/null

# ===== APPLY NETWORK CONDITIONS BASED ON SCENARIO =====
case $SCENARIO in
    1)
        echo "Running Baseline scenario..."
        # No impairment; nothing to add
        ;;
    2)
        echo "Running 5% packet loss scenario..."
        sudo tc qdisc add dev $INTERFACE root netem loss 5%
        ;;
    3)
        echo "Running Delay+Jitter scenario (100ms ±10ms)..."
        sudo tc qdisc add dev $INTERFACE root netem delay 100ms 10ms
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

# ===== START PACKET CAPTURE =====
sudo tcpdump -i $INTERFACE udp -w $PCAP_FILE &
TCPDUMP_PID=$!

# ===== START SERVER =====
python3 /mnt/d/Github/Network-Project/server.py &
SERVER_PID=$!

# ===== GIVE SERVER TIME TO START =====
sleep 2

# ===== START CLIENT =====
python3 /mnt/d/Github/Network-Project/client.py &
CLIENT_PID=$!

# ===== RUN TEST FOR FIXED DURATION =====
sleep $TEST_DURATION

# ===== STOP ALL PROCESSES =====
kill $CLIENT_PID
kill $SERVER_PID
sudo kill $TCPDUMP_PID

# ===== CLEANUP NETEM =====
sudo tc qdisc del dev $INTERFACE root 2>/dev/null

echo "Test complete. Packet capture saved as $PCAP_FILE"

# ========== Analyze Results ===========
python3 /mnt/d/Github/Network-Project/createGraphs.py
