import socket
import struct 
import time
import random
import threading

# ==========================================
#          CLIENT CONFIGURATION
# ==========================================

#Sensor stuff
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

def calculateChecksum(data):
    return sum(data) % 65536

#intervals to send data
dataInterval = 0.02
heartBeatInterval = 5

ackTimeout = 1
maxRetries = 5
packetBuffer = {}
bufferLock = threading.Lock()

#connection stuff                      
serverHost = '127.0.0.1'
serverPort = 5005
sensor = SensorMessage(device_id=1, seq_num=0)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)#AF_INET is for the version and DGRAM IS for UDP connection

print(f"[Client] Device {sensor.device_id} started, sending to {serverHost}:{serverPort}")

seqNumber = 0
lastDataTime = 0

# ==================================
#            FUNCTIONS               
# ==================================

def recieveAck():
    try:
        data, addr = client_socket.recvfrom(256)
        if len(data) >= headerSize:
            msgType, ackDeviceId, ackSeq, _, _, _ = struct.unpack(headerFormat, data[:headerSize])
            if msgType == 3:  # ACK
                print(f"[Client] Received ACK for seq={ackSeq} from device={ackDeviceId}")
                with bufferLock:
                    if ackSeq in packetBuffer:
                        del packetBuffer[ackSeq]
                        print(f"[Client] Removed seq={ackSeq} from buffer")

    except socket.timeout:
        # No ACK received in this check
        pass

def resendPacket():
    currentTime = time.time()
    with bufferLock:
        for seq, info in list(packetBuffer.items()):
            if currentTime - info['timestamp'] > ackTimeout:
                if info['retries'] >= maxRetries:
                    print(f"[Client] Packet seq={seq} dropped after {maxRetries} retries")
                    del packetBuffer[seq]
                else:
                    client_socket.sendto(info['packet'], (serverHost, serverPort))
                    info['timestamp'] = currentTime
                    info['retries'] += 1
                    print(f"[Client] Resent packet seq={seq}, retry={info['retries']}")
                    

def ackAndResendThread():
    while True:
        recieveAck()      
        resendPacket()    
        time.sleep(0.1)   


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
        
        with bufferLock:
                packetBuffer[seqNumber] = {'packet': packet, 'timestamp': time.time(), 'retries': 0}
        
        print(f"[Client] Sent type={msgType}, seq={seqNumber}, batch={batchCount}, checksum={checksum}")

    else:
        # Send each reading alone
        for reading in readings:
            seqNumber += 1
            payload = reading.encode()
            batchCount = 1

            if len(payload) > payloadMaxSize:
                payload = payload[:payloadMaxSize] #truncate bye bye 

            tempHeader = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, 0)
            checksum = calculateChecksum(tempHeader + payload)
            header = struct.pack(headerFormat, msgType, sensor.device_id, seqNumber, timestamp, batchCount, checksum)
            packet = header + payload
            client_socket.sendto(packet, (serverHost, serverPort))
            
            with bufferLock:
                packetBuffer[seqNumber] = {'packet': packet, 'timestamp': time.time(), 'retries': 0}
                
            print(f"[Client] Sent type={msgType}, seq={seqNumber}, batch={batchCount}, checksum={checksum}")

try:
    batchingmode = True
    threading.Thread(target=ackAndResendThread, daemon=True).start()
    
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
