#!/usr/bin/env python3

from concurrent.futures import thread
from http import server
import os
import random
from re import I, T
from select import select
import socket
import signal
import struct
import sys
from telnetlib import STATUS
import threading
from datetime import datetime
from datetime import datetime
import time
from typing import IO

# Fases de registre
REG_REQ = 0x00
REG_ACK = 0x02
REG_NACK = 0x04
REG_REJ = 0X06
ERROR = 0x0F

# Posibles estats del client (UDP)
DISCONNECTED = 0xA0
WAIT_REG_RESPONSE = 0xA2
WAIT_DB_CHECK = 0xA4
REGISTERED = 0XA6
ALIVE = 0xA8

# Paquets fase de manteniment de comunicacio amb el servidor
ALIVE_INF = 0x10
ALIVE_ACK = 0x12
ALIVE_NACK = 0x14
ALIVE_REJ = 0x16

# Paquets per l'enviament de l'arxiu de cfg
SEND_FILE = 0x20
SEND_DATA = 0x22
SEND_ACK = 0x24
SEND_NACK = 0x26
SEND_REJ = 0x28
SEND_END = 0x2A

# Paquets per l'obtencio de l'arxiu de cfg
GET_FILE = 0x30
GET_DATA = 0x32
GET_ACK = 0x34
GET_NACK = 0x36
GET_REJ = 0x38
GET_END = 0x3A

t = 1
p = 2
q = 3
u = 2
n = 6
o = 2

r = 2
s = 3
w = 3

debug_mode = False
authorized_clients = []
sockets = None
servidor = None
class Servidor:
    def __init__(self):
        self.id = None
        self.mac = None

class Client:
    def __init__(self):
        self.id_equip = None
        self.state = DISCONNECTED
        self.num_ale = random.randint(0, 999999)
        self.mac = None
        self.udp_port = None
        self.ip_address = None
        self.consecutive_non_received_alives = 0
        self.is_alive_received = False
        self.is_data_received = False
        self.is_end_data_received = False
        self.data_received_timeout_exceeded = False
        self.conf_tcp_socket = None

class Sockets:
    def __init__(self):
        self.udp_socket = None
        self.udp_port = None

        self.tcp_socket = None
        self.tcp_port = None

def get_time():
    now = datetime.now()
    global current_time
    global current_date_and_time
    current_time = now.strftime("%H:%M:%S")    
    current_date_and_time = now.strftime("%m-%d-%Y, %H:%M:%S")

def convert_type_to_string(type):
    if type == REG_REQ:
        return "REG_REQ"
    elif type == REG_ACK:
        return "REG_ACK"
    elif type == REG_NACK:
        return "REG_NACK"
    elif type == REG_REJ:
        return "REG_REJ"
    elif type == ALIVE_INF:
        return "ALIVE_INF"
    elif type == ALIVE_ACK:
        return "ALIVE_ACK"
    elif type == ALIVE_NACK:
        return "ALIVE_NACK"
    elif type == ALIVE_REJ:
        return "ALIVE_REJ"
    elif type == SEND_FILE:
        return "SEND_FILE"
    elif type == SEND_DATA:
        return "SEND_DATA"
    elif type == SEND_ACK:
        return "SEND_ACK"
    elif type == SEND_NACK:
        return "SEND_NACK"
    elif type == SEND_REJ:
        return "SEND_REJ"
    elif type == SEND_END:
        return "SEND_END"
    elif type == GET_FILE:
        return "GET_FILE"
    elif type == GET_DATA:
        return "GET_DATA"
    elif type == GET_ACK:
        return "GET_ACK"
    elif type == GET_NACK:
        return "GET_NACK"
    elif type == GET_REJ:
        return "GET_REJ"
    else:
        return "GET_END"

def get_status(status):
    if status == DISCONNECTED:
        return "DISCONNECTED"
    elif status == WAIT_REG_RESPONSE:
        return "WAIT_REG_RESPONSE"
    elif status == WAIT_DB_CHECK:
        return "WAIT_DB_CHECK"
    elif status == REGISTERED:
        return "REGISTERED"
    else:
        return "SEND_ALIVE"

def manage_args(argv):
    global sockets
    sockets = Sockets()
    server_file = None
    auth_file = None
    for i in range(len(argv)):
        if argv[i] == "-d":
            global debug_mode
            debug_mode = True
            print("Executant mode debug")
        elif argv[i] == "-c" and len(argv) > i + 1:
            try:
                server_file = open(argv[i+1], "r")
            except IOError:
                print("ERROR a l'obrir el fitxer de configuració especificat")
                sys.exit(1)
        elif argv[i] == "u" and len(argv) > i + 1:
            try:
                auth_file = open(argv[i+1],"r")
            except IOError:
                print("Error en obrir l'arxiu dels clients permesos indicat")
                sys.exit(1)
    if server_file is None:
        try:
            server_file = open("server.cfg","r")
        except IOError:
            print("Error en intentar obrir el fitxer predeterminar")
            sys.exit(1)
    if auth_file is None:
        try:
            auth_file = open("equips.dat","r")
        except IOError:
            print("Error en intatar obrir l'arxiu de clients autoritzats predeterminat")
            sys.exit(1)
    get_authorized_clients(auth_file)
    get_server_data(server_file)

def get_authorized_clients(auth_file):
    global authorized_clients
    num_clients = 0
    for line in auth_file:
        if line != "\n":
            client = Client()
            client_name, client_mac = line.split("\n")[0].split(" ")
            client.id_equip = client_name
            client.mac = client_mac
            authorized_clients.append(client)
            num_clients += 1

    auth_file.close()
    if debug_mode:
        print("DEBUG -> Read " + str(num_clients) + " allowed clients' data")

def get_server_data(server_file):
    global servidor
    global sockets
    servidor = Servidor()
    for line in server_file:
        line = line.strip("\n")
        temp = line.split(" ")
        if temp[0] == "Id":
            servidor.id = temp[1]
        elif temp[0] == "UDP-port":
            sockets.udp_port = int(temp[1])
        elif temp[0] == "TCP-port":
            sockets.tcp_port = int(temp[1])
        elif temp[0] == "MAC":
            servidor.mac = temp[1]
    server_file.close()

def list_clients():
    print("--- ID.Equip ---   ----- STATE -----   --- MAC ---   ------ Random Number ------   ---------------Ip-Address---------------")
    for cli in authorized_clients:
        print("   " + cli.id_equip + "       "  + get_status(cli.state)+ "          " + cli.mac + "         " + str(cli.num_ale))

def setup_UDP_socket():
    global sockets
    sockets.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sockets.udp_socket.bind(("", sockets.udp_port))
    except socket.error:
        print("Error al bind (socket UDP)")

def setup_TCP_socket():
    global sockets
    sockets.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sockets.tcp_socket.bind(("", sockets.tcp_port))
    except socket.error:
        print("Error en el bind (socket TCP)")

def print_accepted_commands():
    print("INFO  -> Accepted commands are:\n" +
            "\t\t    quit -> finishes server\n" +
            "\t\t    list -> lists allowed clients")

def read_from_stdin():
    line = sys.stdin.readline()
    return line.split("\n")[0]

def terminal_input():
    try:
        while True:
            command = read_from_stdin()
            if command == "quit":
                os.kill(os.getpid(), signal.SIGINT)
            elif command == "list":
                list_clients()
            else:
                print("ERROR -> " + command + " is not an accepted command")
                print_accepted_commands()
    except (KeyboardInterrupt, SystemExit):
        return

def service_loop():
    """
    initiates udp and tcp service loops:
    creates a thread (daemon) to initiate tcp loop
    and then initiates udp service loop
    """
    #thread_for_tcp = threading.Thread(target=tcp_service_loop)
    #thread_for_tcp.daemon = True
    #thread_for_tcp.start()

    udp_service_loop()

def udp_service_loop():
    """
    Waits for udp connection,
    when getting connection creates a thread (daemon) to serve it and
    keeps waiting for incoming connections on udp socket
    """
    if debug_mode:
        print("DEBUG -> UDP socket enabled")

    while True:
        received_package_unpacked, client_ip_address, client_udp_port = \
            receive_package_via_udp_from_client(84)

def receive_package_via_udp_from_client(bytes_to_receive):
    received_package_packed, (client_ip_address, client_udp_port) = sockets.udp_socket.\
                                                                    recvfrom(bytes_to_receive)
    received_package_unpacked = struct.unpack('B7s13s7s50s', received_package_packed)
    package_type = received_package_unpacked[0]
    client_name = received_package_unpacked[1].split(b"\x00")[0].decode("utf-8")
    client_mac_address = received_package_unpacked[2].split(b"\x00")[0].decode("utf-8")
    random_num = received_package_unpacked[3].split(b"\x00")[0].decode("utf-8")
    data = received_package_unpacked[4].split(b"\x00")[0].decode("utf-8")

    if debug_mode:
        print("DEBUG -> \t\t Received " + convert_type_to_string(package_type) +
                      "; \n" + "\t\t\t\t\t  Bytes: " + str(bytes_to_receive) + ", \n" +
                      "\t\t\t\t\t  name: " + client_name + ", \n" +
                      "\t\t\t\t\t  mac: " + client_mac_address + ", \n" +
                      "\t\t\t\t\t  rand num: " + random_num + ", \n" +
                      "\t\t\t\t\t  data: " + data + "\n")
    return received_package_unpacked, client_ip_address, client_udp_port

if __name__ == '__main__':
    try:
        manage_args(sys.argv)
        setup_UDP_socket()
        setup_TCP_socket()
        
        global input_thread
        input_thread = threading.Thread(target=terminal_input, daemon=True)
        input_thread.start()

        service_loop()

    except(KeyboardInterrupt, SystemExit):
        print("Sortint del servidor...")
        if 'UDP_socket' in globals():
            sockets.udp_socket.close()
        if 'TCP_socket' in globals():
            sockets.tcp_socket.close()
        sys.exit()
