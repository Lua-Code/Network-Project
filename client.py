import socket
import struct 
import time
import random

def calculateChecksum(data):
    return sum(data) % 65536

class SensorMessage:
    def __init__(self, device_id, seq_num, checksum=None, sensor_data=None, msg_type=1):
        self.device_id = device_id  
        self.seq_num = seq_num
        self.checksum = checksum      
        self.sensor_data = sensor_data  
        self.timestamp = int(time.time())  
        self.msg_type = msg_type  #1 Data #2 heartbeat 

packetSize = 200
headerFormat = "! B H H I B H" #corresponding to our desired header format of the following: msgType > DeviceID > SeqNum > timeStamp > batchCount > checksum, 12 Bytes!
headerSize = struct.calcsize(headerFormat)
payloadMaxSize = packetSize - headerSize

dataInterval = 1
heartBeatInterval = 5
                      
serverHost = '127.0.0.1'
serverPort = 5005
sensor = SensorMessage(device_id=1, seq_num=0)

#connection type 
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)#AF_INET is for the version and DGRAM IS for UDP connection

print(f"[Client] Device {sensor.device_id} started, sending to {serverHost}:{serverPort}")

seqNumber = 0
lastDataTime = 0

def sendPacket(msgType, readings=None, batchingAllowed=False):
    global seqNumber
    timestamp = int(time.time())

    if not readings:
        # Heartbeat packet
        seqNumber += 1
        payload = b""
        batchCount = 0
        tempHeader = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, 0)
        checksum = calculateChecksum(tempHeader + payload)
        header = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, checksum)
        packet = header + payload
        client_socket.sendto(packet, (serverHost, serverPort))
        print(f"[Client] Sent type={msgType}, seq={seqNumber}, batch={batchCount}, checksum={checksum}")
        return

    if batchingAllowed:
        seqNumber += 1
        payloadString = "|".join(readings)
        payload = payloadString.encode()
        batchCount = len(readings)

        if len(payload) > payloadMaxSize:
            payload = payload[:payloadMaxSize]
            batchCount = 0

        tempHeader = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, 0)
        checksum = calculateChecksum(tempHeader + payload)
        header = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, checksum)
        packet = header + payload
        client_socket.sendto(packet, (serverHost, serverPort))
        print(f"[Client] Sent type={msgType}, seq={seqNumber}, batch={batchCount}, checksum={checksum}")

    else:
        # Send each reading alone
        for reading in readings:
            seqNumber += 1
            payload = reading.encode()
            batchCount = 1

            if len(payload) > payloadMaxSize:
                payload = payload[:payloadMaxSize] #truncate

            tempHeader = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, 0)
            checksum = calculateChecksum(tempHeader + payload)
            header = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, checksum)
            packet = header + payload
            client_socket.sendto(packet, (serverHost, serverPort))
            print(f"[Client] Sent type={msgType}, seq={seqNumber}, batch={batchCount}, checksum={checksum}")

try:
    batchingmode = True
    while True:

        if random.random() < 0.8:
            readings = []
            for _ in range(random.randint(1, 3)): 
                temp = round(random.uniform(20, 30), 2)
                hum = round(random.uniform(40, 60), 2)
                readings.append(f"temp={temp},hum={hum}")
            sendPacket(1, readings,batchingmode)
            lastDataTime = time.time()
        else:
            if time.time() - lastDataTime >= heartBeatInterval:
                sendPacket(2)
                lastDataTime = time.time()
        time.sleep(dataInterval)

except KeyboardInterrupt:
    print("\n[Client] Stopped.")
