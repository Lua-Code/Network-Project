import socket, struct, time, csv, os, signal

# =====================================
#       SERVER CONFIGURATION
# =====================================
serverIp = "127.0.0.1"
serverPort = 5005
scriptDir = os.path.dirname(os.path.abspath(__file__))
csvFile = os.path.join(scriptDir, "Telemetry_Results.csv")
shutdown_flag = False

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allows quick restart
serverSocket.bind((serverIp, serverPort))
serverSocket.settimeout(1.0)  # 1-second timeout for graceful shutdown

print("Meow, Server is Up and running!")

headerFormat = "! B H H I B H"
headerSize = struct.calcsize(headerFormat)

deviceState = {}  # keep track of duplicates
timeStampOrderedPackets = []  # offline ordering after shutdown

# =====================================
#       FUNCTIONS
# =====================================
def calculateChecksum(data):
    return sum(data) % 65536

def signal_handler(sig, frame):
    global shutdown_flag
    print(f"\n[Server] Received signal {sig}, shutting down...")
    shutdown_flag = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def sendAck(deviceId, seqNum, clientAddress):
    msgType = 3
    timestamp = int(time.time())
    batchCount = 0
    payload = b""

    tempHeader = struct.pack(headerFormat, msgType, deviceId, seqNum, timestamp, batchCount, 0)
    checksum = calculateChecksum(tempHeader + payload)
    header = struct.pack(headerFormat, msgType, deviceId, seqNum, timestamp, batchCount, checksum)
    packet = header + payload

    serverSocket.sendto(packet, clientAddress)
    print(f"[Server] Sent ACK to Device:{deviceId}, Seq:{seqNum}, Checksum:{checksum}")

def receiveMessageAndSendAck(data, clientAddress, csvWriter, x):
    totalBytes = len(data)
    arrivalTime = time.time()
    CPUStart = time.perf_counter()

    msgType, deviceId, seqNum, timeStamp, batchCount, checksum = struct.unpack(
        headerFormat, data[:headerSize]
    )
    payload = data[headerSize:]

    noChecksumHeader = struct.pack(headerFormat, msgType, deviceId, seqNum, timeStamp, batchCount, 0)
    ourChecksum = calculateChecksum(noChecksumHeader + payload)
    validCheckSumFlag = (checksum == ourChecksum)

    duplicateFlag, gapFlag = 0, 0

    if deviceId not in deviceState:
        deviceState[deviceId] = set()

    if seqNum in deviceState[deviceId]:
        duplicateFlag = 1
    elif deviceState[deviceId] and seqNum > max(deviceState[deviceId]) + 1:
        gapFlag = 1

    deviceState[deviceId].add(seqNum)

    if payload:
        readings = payload.decode(errors="ignore").split("|")
        print(f"[Server] Device:{deviceId}, Seq:{seqNum}, Type={msgType}, Batch={batchCount}, "
              f"Checksum:{'OK' if validCheckSumFlag else 'BAD'}, Dup:{duplicateFlag}, Gap:{gapFlag}")
        for i, r in enumerate(readings):
            print(f"  Reading {i}: {r}")

    CPUEnd = time.perf_counter()
    CPUTime = (CPUEnd - CPUStart) * 1000

    # Write to main CSV
    csvWriter.writerow([
        msgType, deviceId, seqNum, timeStamp, batchCount,
        validCheckSumFlag, arrivalTime, duplicateFlag,
        gapFlag, totalBytes, CPUTime
    ])
    x.flush()

    # Store for sorted CSV
    timeStampOrderedPackets.append({
        "msgType": msgType,
        "deviceId": deviceId,
        "seqNum": seqNum,
        "timeStamp": timeStamp,
        "batchCount": batchCount,
        "validCheckSumFlag": validCheckSumFlag,
        "arrivalTime": arrivalTime,
        "duplicateFlag": duplicateFlag,
        "gapFlag": gapFlag,
        "totalBytes": totalBytes,
        "CPUTime": CPUTime,
    })

    sendAck(deviceId, seqNum, clientAddress)

# =====================================
#       MAIN LOOP
# =====================================
with open(csvFile, "w", newline="") as x:
    csvWriter = csv.writer(x)
    csvWriter.writerow([
        "Message Type", "Device_ID", "Sequence Number", "Timestamp", "Batch Count",
        "Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag",
        "Bytes Per Report", "CPU Time Per Report(ms)"
    ])

with open(csvFile, "a", newline="") as x:
    csvWriter = csv.writer(x)
    try:
        while not shutdown_flag:
            try:
                data, clientAddress = serverSocket.recvfrom(256)
                receiveMessageAndSendAck(data, clientAddress, csvWriter, x)
            except socket.timeout:
                continue
    except Exception as e:
        print(f"\n[Server] Exception caught: {e}")
    finally:
        print("[Server] Saving sorted telemetry...")
        # Sort by timestamp
        timeStampOrderedPackets.sort(key=lambda p: p["timeStamp"])
        sortedFile = os.path.join(scriptDir, "Telemetry_Results_sorted.csv")
        with open(sortedFile, "w", newline="") as sortedCsv:
            writer = csv.writer(sortedCsv)
            writer.writerow([
                "Message Type", "Device_ID", "Sequence Number", "Timestamp", "Batch Count",
                "Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag",
                "Bytes Per Report", "CPU Time Per Report(ms)"
            ])
            for pkt in timeStampOrderedPackets:
                writer.writerow([
                    pkt["msgType"], pkt["deviceId"], pkt["seqNum"],
                    pkt["timeStamp"], pkt["batchCount"], pkt["validCheckSumFlag"],
                    pkt["arrivalTime"], pkt["duplicateFlag"], pkt["gapFlag"],
                    pkt["totalBytes"], pkt["CPUTime"]
                ])
        print("[Server] Shutdown complete. Telemetry saved.")
