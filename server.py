import socket, struct, time, csv, os,signal

# =====================================
#       Our Server Configuraiton
# =====================================

serverIp = "127.0.0.1"
serverPort = 5005
scriptDir = os.path.dirname(os.path.abspath(__file__))
csvFile = os.path.join(scriptDir, "Telemetry_Results.csv")
shutdown_flag = False

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.bind((serverIp, serverPort))

print("Meow, Server is Up and running!")

headerFormat = "! B H H I B H"
headerSize = struct.calcsize(headerFormat)

def calculateChecksum(data):
    return sum(data) % 65536

deviceState = {} # just to keep an eye on duplicates
timeStampOrderedPackets = [] #for offline ordering after server shuts down


# ============================
#       FUNCTIONS
# ============================

def signal_handler(sig, frame):
    global shutdown_flag
    print(f"\n[Server] Received signal {sig}, shutting down...")
    shutdown_flag = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def sendAck(deviceId, seqNum, clientAddress):
    msgType = 3  # 3 for ack
    timestamp = int(time.time())
    batchCount = 0
    payload = b""  

    # Temporary header with checksum 0 for calculation
    tempHeader = struct.pack(headerFormat, msgType, deviceId, seqNum, timestamp, batchCount, 0)
    checksum = calculateChecksum(tempHeader + payload)

    # Final header with real checksum
    header = struct.pack(headerFormat, msgType, deviceId, seqNum, timestamp, batchCount, checksum)
    packet = header + payload

    # Send ACK
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
        payloads_str = payload.decode(errors="ignore")
        readings = payloads_str.split("|")
        print(f"[Server] Device:{deviceId}, Sequence Number:{seqNum}, Message Type={msgType} "
              f"Batch Count: {batchCount} Checksum Validity:{'OK' if validCheckSumFlag else 'BAD'} "
              f"Duplicate Flag:{duplicateFlag} Gap Flag:{gapFlag}")

        for index, reading in enumerate(readings):
            print(f"  Reading {index}: {reading}\n")

    CPUEnd = time.perf_counter()
    CPUTime = (CPUEnd - CPUStart) * 1000

    csvWriter.writerow([
        msgType, deviceId, seqNum, timeStamp, batchCount,
        validCheckSumFlag, arrivalTime, duplicateFlag,
        gapFlag, totalBytes, CPUTime
    ])
    x.flush()

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
    
    sendAck(deviceId,seqNum,clientAddress)


with open(csvFile, "w", newline="") as x:
    csvWriter = csv.writer(x)
    csvWriter.writerow(["Message Type","Device_ID", "Sequence Number", "Timestamp","Batch Count",
                        "Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag",
                        "Bytes Per Report", "CPU Time Per Report(ms)"])

with open(csvFile, "a", newline="") as x:
    csvWriter = csv.writer(x)

    try:
        while True:
            data, clientAddress = serverSocket.recvfrom(256)
            receiveMessageAndSendAck(data, clientAddress, csvWriter, x)
    except KeyboardInterrupt:
        print("\n[Server] KeyboardInterrupt caught, stopping.")
    except Exception as e:
        print(f"\n[Server] Exception caught: {e}")
    finally:
        print("[Server] Saving sorted telemetry...")
        timeStampOrderedPackets.sort(key=lambda p: p["timeStamp"])
        with open("Telemetry_Results_sorted.csv", "w", newline="") as sortedCsv:
            writer = csv.writer(sortedCsv)
            writer.writerow(["Message Type","Device_ID", "Sequence Number", "Timestamp","Batch Count",
                            "Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag",
                            "Bytes Per Report", "CPU Time Per Report(ms)"])

            for pkt in timeStampOrderedPackets:
                writer.writerow([
                    pkt["msgType"], pkt["deviceId"], pkt["seqNum"],
                    pkt["timeStamp"], pkt["batchCount"], pkt["validCheckSumFlag"],
                    pkt["arrivalTime"], pkt["duplicateFlag"], pkt["gapFlag"],
                    pkt["totalBytes"], pkt["CPUTime"]
                ])
