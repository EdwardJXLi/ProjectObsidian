import socket
import struct
import gzip
import io
import threading
import os
import sys
import signal
import sched
import datetime

import time

enableFakeLag = False
handleCTLc = False
version = "protocoltestV4"

connections = []
players = {}

def fakeLag(t):
    if(enableFakeLag):
        time.sleep(t)

def sendToAllPlayers(msg, clientSelf = None, checkSelf = False):
    for client in players.keys():
        if(client != clientSelf or checkSelf == False):
            client.send(msg)
            print(f"SERVER -> CLIENT ID {getConnId(client)} [{msg}]")

def delClient(client):
    connections[getConnId(client)] = None
    del players[client]
    print("Client Cleaned Up!")
    clearUserCache()

def saveMap():
    print("Saving World...")
    with gzip.open("./map.gz", "wb+") as f:
	    f.write(struct.pack('!I', len(mapData)) + bytes(mapData))
    print("World Saved To map.gz!!")

def backupMap():
    print("Backing Up World...")
    now = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    backupName = f"./backups/backup-{now}.gz"
    with gzip.open(backupName, "wb+") as f:
	    f.write(struct.pack('!I', len(mapData)) + bytes(mapData))
    print("World Backed Up To {}.gz!!")
    return backupName

def getConnId(conn):
    return players[conn]['id']

def getOnlinePlayers():
    count = 0
    for c in connections:
        if(c != None):
            count = count + 1
    return count

def clearUserCache():
    print("Attempting to clear user cache")
    global connections
    global players
    if(getOnlinePlayers() == 0):
        connections = []
        players = {}
        print("User cache CLEARED!!")

def handleCommand(client, command):
    #Main Commands
    if(command == "help"):
        #Generate Help
        helpInfo = [
            f"&d================================",
            f"&eAvailable Commands:",
            f"&a/help&f - &bHelp Menu",
            f"&a/about&f - &bInformation about server",
            f"&a/save&f - &bSave Map",
            f"&a/backup&f - &bBackup Map to Read only file",
            f"&a/motd&f - &bprint MOTD",
            f"&d================================"
        ]
        #Send Help
        print(f"========== COMMAND: print HELP ==========")
        for helpLine in helpInfo:
            client.send(struct.pack("BB64s", 13, 0, bytes(helpLine.ljust(64), "ascii")))
    elif(command == "about"):
        #Generate About
        about = [
            f"&b================================",
            f"todo",
            f"&b================================"
        ]
        #Send About
        print(f"========== COMMAND: print ABOUT ==========")
        for aboutLine in about:
            client.send(struct.pack("BB64s", 13, 0, bytes(aboutLine.ljust(64), "ascii")))
    elif(command == "save"):
        #Save Map Command
        print(f"========== COMMAND: MAP SAVE ==========")
        saveMessage = struct.pack("BB64s", 13, 0, bytes(f"&aMap Saving...", "ascii"))
        sendToAllPlayers(saveMessage)
        saveMap()
        saveMessage2 = struct.pack("BB64s", 13, 0, bytes(f"&aMap Saved!", "ascii"))
        sendToAllPlayers(saveMessage2)
    elif(command == "backup"):
        #Backup Map Command
        print(f"========== COMMAND: MAP BACKUP ==========")
        backupMessage = struct.pack("BB64s", 13, 0, bytes(f"&aStarting Map Backup...", "ascii"))
        sendToAllPlayers(backupMessage)
        backupName = backupMap()
        backupMessage2 = struct.pack("BB64s", 13, 0, bytes(f"&aBackup Completed!", "ascii"))
        sendToAllPlayers(backupMessage2)
        backupMessage3 = struct.pack("BB64s", 13, 0, bytes(f"&aBackup Saved To: {backupName}", "ascii"))
        sendToAllPlayers(backupMessage3)
    elif(command == "motd"):
        #Generate MOTD
        motd = [
            f"&a==============================================================",
            f"&ePython-Based Minecraft Clasic",
            f"&eServer Reverse Engineer and",
            f"&eReimplementation Project",
            f"&bVersion: 0 | &9Protocol: v7&f | &aPlayers Online: {getOnlinePlayers()}&f",
            f"This server contains &4~ABSOLUTELY NO~&f Minecraft / Mojang code",
            f"&eRun &d/help&e or &d/about&e to learn more!",
            f"&a(c)RadioactiveHydra 2020",
            f"&a=============================================================="
        ]
        #Send MOTD
        print(f"========== COMMAND: print MOTD ==========")
        for motdLine in motd:
            client.send(struct.pack("BB64s", 13, 0, bytes(motdLine.ljust(64), "ascii")))
    #Debug Commands
    elif(command == "testerror"):
        raise Exception("Test Error")
    #elif(command == "stop"):
    #    handleCTLc = True
    #    print('Starting Shutdown Process\n')
    #    sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4~~!! SERVER SHUTTING DOWN IN !!~~", "ascii")))
    #    countdown = 5
    #    while(countdown != 0):
    #        sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4  {countdown}", "ascii")))
    #        countdown = countdown - 1
    #        time.sleep(1)
    #    time.sleep(1)
    #    stopMessage = struct.pack("B64s", 14, bytes(f"Server is Shutting Down!", "ascii"))
    #    sendToAllPlayers(stopMessage)
    #    saveMap()
    #    print('SERVER EXITING\n')
    #    print(f"Server Stopping!!")
    #    print(f"GOODBYE!!!")
    #    sys.exit(0)
    #
    #Unknown Command Handler
    else:
        #Unknown Command
        print(f"========== COMMAND: UNKNOWN COMMAND ==========")
        client.send(struct.pack("BB64s", 13, 0, bytes(f"&cUnknown Command {command}".ljust(64), "ascii")))

def handlePacket(clientPacket, username, conn, pid):
    try:
        if(pid == 13):
            if(len(clientPacket) != 66):
                sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{username} sent malformed packet {13} {len(clientPacket)}", "ascii")))
            else:
                movementChunks = [clientPacket[i: i + 66] for i in range(0, len(clientPacket), 66)]
                for movementChunk in movementChunks:
                    mPID, unused, message = struct.unpack("BB64s", movementChunk[:66])
                    message = message.decode("ascii").strip()

                    if(message[0] == "/"):
                        handleCommand(conn, message[1:])
                    else:
                        messageContent = f"<&b{username} &9(User Id {getConnId(conn)}) &f> {message[:46]}"
                        print(f"!MESSAGE! >>>> {messageContent}")
                        responseMessage = struct.pack("BB64s", 13, 0, bytes(messageContent, "ascii"))
                        sendToAllPlayers(responseMessage)
        elif(pid == 5):
            if(len(clientPacket) != 9):
                sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{username} sent malformed packet {5} {len(clientPacket)}", "ascii")))
            else:
                setBlockChunks = [clientPacket[i: i + 9] for i in range(0, len(clientPacket), 9)]
                for setBlockChunk in setBlockChunks:
                    bPID, x, y, z, mode, blockType = struct.unpack("!BhhhBB", setBlockChunk[:9])
                    print(f"Block {blockType} action {mode} at {x} {y} {z}")
                    if(mode == 0):
                        blockType = 0
                    mapData[x + 256 * (z + 256 * y)] = blockType
                    setBlockMessage = struct.pack("!BhhhB", 6, x, y, z, blockType)
                    sendToAllPlayers(setBlockMessage)
        elif(pid == 8):
            if(len(clientPacket) != 10):
                sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{username} sent malformed packet {8} {len(clientPacket)}", "ascii")))
            else:
                movementChunks = [clientPacket[i: i + 10] for i in range(0, len(clientPacket), 10)]
                for movementChunk in movementChunks:
                    pPID, playerID, x, y, z, yaw, pitch = struct.unpack("!BBhhhBB", movementChunk[:10])

                    dx = x - players[conn]['x']
                    dy = y - players[conn]['y']
                    dz = z - players[conn]['z']
                    dyaw = yaw - players[conn]['yaw']
                    dpitch = pitch - players[conn]['pitch']
                    print(f"Player {getConnId(conn)} Moved To {x} {y} {z} {yaw} {pitch} (CHANGE: {dx} {dy} {dz} {dyaw} {dpitch})")

                    players[conn]['x'] = x
                    players[conn]['y'] = y
                    players[conn]['z'] = z
                    players[conn]['yaw'] = yaw
                    players[conn]['pitch'] = pitch

                    #print(dx, dy, dz, dyaw, dpitch)
                    for client in players.keys():
                        if(client != conn):
                            #if(CalcDistance() > 2):
                            #    teleportMessage = struct.pack("!BBhhhBB", 8, getConnId(conns), x, y, z, yaw, pitch)
                            #    client.send(movementMessage)
                            #else:
                            if(dx != 0 or dy != 0 or dz != 0 or dyaw != 0 or dpitch != 0):
                                #if(dx >= -128 and dx <= 127 and dy >= -128 and dy <= 127 and dz >= -128 and dz <= 127 and dyaw >= -128 and dyaw <= 127 and dpitch >= -128 and dpitch <= 127):
                                #print(getConnId(conn), x, y, z, yaw, pitch, " | ",players[conn]['x'], players[conn]['y'], players[conn]['z'], players[conn]['yaw'], players[conn]['pitch'], " | ", dx, dy, dz, dyaw, dpitch)
                                #movementMessage = struct.pack("!BBbbbbb", 9, getConnId(conn), dx, dy, dz, dyaw, dpitch)
                                #else:
                                movementMessage = struct.pack("!BBhhhBB", 8, getConnId(conn), x, y, z, yaw, pitch)
                                #movementMessage = struct.pack("BBbbbbb", 10, getConnId(conn), dx, 0, 0, 0, 0)
                                #movementMessage = struct.pack("BBbbb", 10, getConnId(conn), dx, dy, dz)
                                print(f"MOVEMENT PACKET ----- SERVER -> CLIENT ID {getConnId(client)} [{movementMessage}]")
                                client.send(movementMessage)
    except Exception as e:
        try:
            sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4Internal Server Error!", "ascii")))
            sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{sys.exc_info()[:64]}", "ascii")))
        except:
            pass
        print("==================================================\n\n\n\n\n\n\n")
        print(e)
        print(sys.exc_info())
        print("==================================================\n\n\n\n\n\n\n")

def thingThread(conn, addr):

    print(f"GZipping Map")

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=1) as f:
        f.write(struct.pack('!I', len(mapData)) + bytes(mapData))

    freshPayload = buf.getvalue()

    print(f"Zipped Map! GZ SIZE: {len(freshPayload)}")

    fakeLag(0.2)

    clientInfo = conn.recv(1024)
    print(f"CLIENT -> SERVER [{clientInfo}]")
    packetID, pVersion, username, verifyKey, unused = struct.unpack("BB64s64sB", clientInfo)
    username = username.decode("ascii").strip()
    verifyKey = verifyKey.decode("ascii").strip()
    print(f"{username} Joined With Packet {packetID}")

    #input()
    fakeLag(0.2)

    response = struct.pack("BB64s64sB", 0, 7, bytes(f"PYTHON TEST SERVER".ljust(64), "ascii"), bytes(f"Supports: c0.30 | Protocol: v7 | Players Online: {getOnlinePlayers()}".ljust(64), "ascii"), 64)
    conn.send(response)
    print(f"SERVER -> CLIENT [{response}]")
    print(f"Response {response} Sent!")

    #input()
    fakeLag(0.4)

    conn.send(b'\2')
    print(f"SERVER -> CLIENT [{2}]")
    print(f"Map INIT Sent!")

    #input()
    fakeLag(0.2)

    print(f"Attempting to send MAP")
    chunks = [freshPayload[i: i + 1024] for i in range(0, len(freshPayload), 1024)]

    for chunkCount, chunk in enumerate(chunks):
        #print(len(chunks), chunkCount, bytes(chunk))
        cDAT = struct.pack("!Bh1024sB", 3, len(chunk), bytes(chunk).ljust(1024, b'\0'), int((100 / len(chunks)) * chunkCount))
        print(f"Sending Chunk {chunkCount+1} out of {len(chunks)} - SIZE: {len(chunk)} bytes")
        conn.send(cDAT)
        print(f"SERVER -> CLIENT (ONLY SHOWING FIRST 20 CHARS) [{cDAT[:20]}]")
        fakeLag(0.07)

    print(f"MAP SENT!!!")

    doneMap = struct.pack("!Bhhh", 4, 256, 64, 256)
    conn.send(doneMap)
    print(f"SERVER -> CLIENT [{doneMap}]")
    print(f"MAP FIN Sent!")
    fakeLag(0.2)

    #Adding user to client pool
    #Get Id
    #connections.index(conn)
    connections.append(conn)
    players[conn] = dict()
    players[conn]["username"] = username
    players[conn]["id"] = connections.index(conn)
    players[conn]["inGame"] = True
    players[conn]["x"] = 0 * 32 + 51
    players[conn]["y"] = 0 * 32 + 51
    players[conn]["z"] = 0 * 32 + 51
    players[conn]["yaw"] = 0
    players[conn]["pitch"] = 0
    print(f"Adding Client {conn} To Client Pool!")

    spawn = struct.pack("!BB64shhhBB", 7, 255, bytes(username.ljust(64), "ascii"), 0 * 32 + 51, 33 * 32 + 51, 0 * 32 + 51, 64, 0)
    conn.send(spawn)
    print(f"SPAWN Sent!")

    #MOTD Information
    motd = [
        f"&a================================",
        f"&ePython-Based Minecraft Clasic",
        f"&eServer Reverse Engineer and",
        f"&eReimplementation Project",
        f"&bServer Software Version: {version} (Python {sys.version.split(' ')[0]})",
        f"&dSupports: c0.30 | &9Protocol: v7&f | &aPlayers Online: {getOnlinePlayers()}&f",
        f"This server contains &4~ABSOLUTELY NO~&f Minecraft / Mojang code",
        f"&eRun &d/help&e or &d/about&e to learn more!",
        f"&a(c)RadioactiveHydra 2020",
        f"&a================================"
    ]

    #Send MOTD
    for motdLine in motd:
        conn.send(struct.pack("BB64s", 13, 0, bytes(motdLine.ljust(64), "ascii")))

    #Send Join Message
    sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&e{username} Joined &9(ID {getConnId(conn)})&f", "ascii")))

    #Send Player Join To All Clients
    spawnPlayer = struct.pack("!BB64shhhBB", 7, getConnId(conn), bytes(username.ljust(64), "ascii"), 0 * 32 + 51, 33 * 32 + 51, 0 * 32 + 51, 64, 0)
    sendToAllPlayers(spawnPlayer, clientSelf=conn, checkSelf=True)

    #Send Current Player Info To Joining Player
    for client in players.keys():
        if(client != conn):
            print(players[client]['x'], players[client]['y'], players[client]['z'])
            clientSpawnPlayer = struct.pack("!BB64shhhBB", 7, getConnId(client), bytes(players[client]["username"], "ascii"), players[client]['x'], players[client]['y'], players[client]['z'], players[client]['yaw'], players[client]['pitch'])
            conn.send(clientSpawnPlayer)
            print(f"SERVER -> CLIENT ID {getConnId(client)} [{clientSpawnPlayer}]")

    while True:
        clientPacket = conn.recv(16384)
        #try:
        print(f"CLIENT -> SERVER [{clientPacket}]")
        if(clientPacket == b""):
            timerThread = threading.Timer(0.2, delClient, args=(conn,))
            timerThread.daemon = True
            timerThread.start()
            print(f"CLIENT DISCONNECTED!")
            sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&ePlayer {username} Left &9(Id {getConnId(conn)})&f", "ascii")), clientSelf=conn, checkSelf=True)
            despawnPlayer = struct.pack("BB", 12, getConnId(conn))
            sendToAllPlayers(despawnPlayer, clientSelf=conn, checkSelf=True)
            break
        else:
            packetOffset = 0
            while(packetOffset < len(clientPacket)):
                pid = struct.unpack("B", clientPacket[packetOffset:+packetOffset + 1])[0]
                newClientPacket = bytes()
                if(pid == 13):
                    #66
                    packetSize = 66
                elif(pid == 5):
                    #9
                    packetSize = 9
                elif(pid == 8):
                    #10
                    packetSize = 10
                else:
                    sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{username} sent invalid packet {pid}", "ascii")))
                    packetSize = 1024
                if(packetOffset+packetSize > len(clientPacket)):
                    sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{username} Packet Size Error {len(clientPacket)} {packetOffset+packetSize}", "ascii")))
                    print(f"!!!!!!\n{clientPacket}\n!!!!!!!!")
                try:
                    newClientPacket = clientPacket[packetOffset:packetOffset+packetSize]
                    packetOffset = packetOffset + packetSize
                    handlePacket(newClientPacket, username, conn, pid)
                except Exception as e:
                    try:
                        print("PACKET HANDLER ERROR")
                        print(sys.exc_info())
                        sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4Packet Handler Error {e}", "ascii")))
                        sendToAllPlayers(struct.pack("BB64s", 13, 0, bytes(f"&4{sys.exc_info()[:64]}", "ascii")))
                    except:
                        print("BIG ERROR!!!!!!!!!!!!!!!!!!!!!!!!!!")




print(f"SERVER STARTING")

print(f"Checking If Map Exists!")

if(os.path.exists("./map.gz")):
    print(f"Reading Save File!")

    payload = open("./map.gz", "rb").read()

    print(f"Verifing Integrety")


    if(payload[0] == 31 and payload[1] == 139):
        print(f"GZ Magic Number Check Pass")
    else:
        raise ValueError(f'Invalid GZIP File! HEADERS ARE {payload[0]} and {payload[1]}')

    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as f:
        checkPayload = f.read()

    payloadLength = struct.unpack('!I', checkPayload[:4])[0]
    payloadData = checkPayload[4:]

    if payloadLength != len(payloadData):
        raise ValueError('Invalid world data file!')
    else:
        print(f"Size Check Pass! {payloadLength} = {len(payloadData)}")

    print(f"INTEGREY PASS!")

    mapData = list(payloadData)

else:
    print(f"Generating MAP!")

    mapData = bytearray(256 * 64 * 256)

    for x in range(256):
        for y in range(64):
            for z in range(256):
                mapData[x + 256 * (z + 256 * y)] = 0 if y > 32 else (2 if y == 32 else 3)

    print(f"Map Generated! MAP SIZE: {len(mapData)} bytes")

    print(f"GZipping Map")

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=1) as f:
        f.write(struct.pack('!I', len(mapData)) + bytes(mapData))

    payload = buf.getvalue()

    print(f"Zipped Map! GZ SIZE: {len(payload)}")

    print(f"Verifing Integrety")


    if(payload[0] == 31 and payload[1] == 139):
        print(f"GZ Magic Number Check Pass")
    else:
        raise ValueError(f'Invalid GZIP File! HEADERS ARE {payload[0]} and {payload[1]}')

    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as f:
        checkPayload = f.read()

    payloadLength = struct.unpack('!I', checkPayload[:4])[0]
    payloadData = checkPayload[4:]

    if payloadLength != len(payloadData):
        raise ValueError('Invalid world data file!')
    else:
        print(f"Size Check Pass! {payloadLength} = {len(payloadData)}")

    print(f"INTEGREY PASS!")


def signal_handler(sig, frame):
    global handleCTLc
    #Hard system stop. Unrecomended!
    if(handleCTLc == False):
        handleCTLc = True
        print('Starting Shutdown Process\n')
        stopMessage = struct.pack("B64s", 14, bytes(f"Server is Shutting Down!", "ascii"))
        sendToAllPlayers(stopMessage)
        saveMap()
        print('SERVER EXITING\n')
        print(f"Server Stopping!!")
        print(f"GOODBYE!!!")
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

print("Starting Server!!")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("0.0.0.0", 1111))
s.listen(5)

print("Listening to connections!")

while True:

    conn, addr = s.accept()
    print(f"New Connection From {addr}")
    print(f"Creating Thread!")
    playerThread = threading.Thread(target=thingThread, args=(conn, addr,))
    playerThread.daemon = True
    playerThread.start()