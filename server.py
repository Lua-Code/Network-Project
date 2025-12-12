import socket, struct, time, csv, os

#Our Server Configuraiton
serverIp = "127.0.0.1"
serverPort = 5005
# CSV file created next to server.py at runtime
scriptDir = os.path.dirname(os.path.abspath(__file__))
csvFile = os.path.join(scriptDir, "Telemetry_Results.csv")

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.bind((serverIp, serverPort))

print("Meow, Server is Up and running!")

#Our Header Format ;p
headerFormat = "! B H H I B H" #corresponding to our desired header format of the following: msgType > DeviceID > SeqNum > timeStamp > batchCount > checksum, 12 Bytes!
headerSize = struct.calcsize(headerFormat)

#CheckSum to check for Validity
def calculateChecksum(data):
    return sum(data) % 65536

#CSV intitation
with open(csvFile, "w", newline="") as x: #Write mode to clear the old data
    csvWriter = csv.writer(x)
    csvWriter.writerow(["Message Type","Device_ID", "Sequence Number", "Timestamp","Batch Count","Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag","Bytes Per Report", "CPU Time Per Report(ms)"])


deviceState = {} #will be used for our duplicate and gap detection

timeStampOrderedPackets = [] #will be used to sort all packets by timestamp after server shtus down

with open(csvFile, "a", newline="") as x: #Append mode btw
    csvWriter = csv.writer(x)
    
    try:     
        while True:
            data, clientAddress = serverSocket.recvfrom(256) #bit bigger than the required 200 Bytes per UDP just incase!
            totalBytes = len(data)
            arrivalTime = time.time()
            CPUStart = time.perf_counter()


            msgType, deviceId, seqNum, timeStamp, batchCount, checksum = struct.unpack(headerFormat,data[:headerSize]) #lets read the header aka our labels ;3
            payload = data[headerSize:]

            noChecksumHeader = struct.pack(headerFormat, msgType, deviceId, seqNum, timeStamp, batchCount, 0)
            ourChecksum = calculateChecksum(noChecksumHeader + payload)
            validCheckSumFlag = (checksum == ourChecksum)

            duplicateFlag, gapFlag = 0, 0
            lastSequenceNum = deviceState.get(deviceId)

            
            if lastSequenceNum is not None: #aka it exists
                if seqNum == lastSequenceNum:
                    duplicateFlag = 1
                elif seqNum > lastSequenceNum + 1:
                    gapFlag = 1
            deviceState[deviceId] = seqNum

            if payload: 
                payloads_str = payload.decode(errors="ignore")
                readings = payloads_str.split("|")                  
                print(f"[Server] Device:{deviceId}, Sequence Number:{seqNum}, Message Type={msgType} "
                        f"Batch Count: {batchCount} Checksum Validity:{'OK' if validCheckSumFlag else 'BAD'} "
                        f"Duplicate Flag:{duplicateFlag} Gap Flag:{gapFlag}")
                
                for index,reading in enumerate(readings):

                    print(f"  Reading {index}: {reading}\n")
            
            CPUEnd = time.perf_counter()   
            CPUTime = (CPUEnd-CPUStart)*1000
            #let's log results in the csv file
            csvWriter.writerow([msgType, deviceId, seqNum, timeStamp, batchCount, validCheckSumFlag, arrivalTime,
                                duplicateFlag, gapFlag,totalBytes,CPUTime])
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
    except KeyboardInterrupt:
            print("\n[Server] Stopped.")
            timeStampOrderedPackets.sort(key=lambda p: p["timeStamp"])
            with open("Telemetry_Results_sorted.csv", "w", newline="") as sortedCsv:
                writer = csv.writer(sortedCsv)
                writer.writerow(["Message Type","Device_ID", "Sequence Number", "Timestamp","Batch Count",
                                "Valid Checksum", "Arrival", "Duplicate Flag", "Gap Flag",
                                "Bytes Per Report", "CPU Time Per Report(ms)"])
                for pkt in timeStampOrderedPackets:
                    writer.writerow([pkt["msgType"], pkt["deviceId"], pkt["seqNum"], pkt["timeStamp"], pkt["batchCount"],
                                    pkt["validCheckSumFlag"], pkt["arrivalTime"], pkt["duplicateFlag"], pkt["gapFlag"],
                                    pkt["totalBytes"], pkt["CPUTime"]])

