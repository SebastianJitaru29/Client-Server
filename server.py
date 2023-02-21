from concurrent.futures import thread
from http import server
import os
import random
from re import I, T
from select import select
import socket
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
server = None
sockets = None

class Servidor:
    def __init__(self):
        self.id = None
        self.mac = None

class Client:
    def __init__(self):
        self.name = None
        self.state = "DISCONNECTED"
        self.random_num = random.randint(0, 999999)
        self.mac_address = None
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
    auth_file = None
    server_file = None
    for i in range(len(argv)):
        if argv[i] == "-d":
            global debug_mode
            debug_mode = True
            print("Executant el mode debug")
        elif argv[i] == "-c" and len(argv) > i + 1:
            try:
                server_file = open(argv[i+1], "r")
            except IOError:
                print("ERROR a l'obrir el fitxer de configuració especificat")
                sys.exit(1)
        elif argv[i] == "-u" and len(argv) > i + 1:
            try:
                auth_file = open(argv[i+1], "r")
            except IOError:
                print("ERROR a l'obrir el fitxer de clients especificat")
                sys.exit(1)

        if server_file is None:
            try:
                server_file = open("server.cfg", "r")
            except IOError:
                print("ERROR a l'obrir el fitxer predeterminat")
                sys.exit(1)

        if auth_file is None:
            try:
                auth_file = open("equips.dat", "r")
            except IOError:
                print("ERROR a l'obrir el fitxer de clients predeterminat")
                sys.exit(1)

    # es guarda en un array els clients autoritzats

    global authorized_clients
    for line in auth_file:
        if line != "\n":
            line = line.strip("\n")
            cli = Client()
            cli.id_disp = line
            authorized_clients.append(cli)
    auth_file.close()

    # es guarda en una instància Servidor les dades del fitxer

    global server
    server = Servidor()
    for line in server_file:
        line = line.strip("\n")
        temp = line.split(" = ")
        if temp[0] == "Id":
            server.id = temp[1]
        elif temp[0] == "UDP-port":
            socket.UDP_port = int(temp[1])
        elif temp[0] == "TCP-port":
            socket.TCP_port = int(temp[1])
    server_file.close()

def setup_UDP_socket():
    Sockets.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        Sockets.udp_socket.bind(("", Sockets.udp_port))
    except socket.error:
        print("Error al bind (socket UDP)")

def setup_TCP_socket():
    Sockets.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        Sockets.tpc_socket.bind(("", Sockets.tcp_port))
    except socket.error:
        print("Error en el bind (socket TCP)")

if __name__ == '__main__':
    try:

        manage_args(sys.argv)
        setup_UDP_socket()
        setup_TCP_socket()

    except(KeyboardInterrupt, SystemExit):
        print("Sortint del servidor...")
        if 'UDP_socket' in globals():
            Sockets.udp_socket.close()
        if 'TCP_socket' in globals():
            Sockets.tcp_socket.close()
        os._exit(0)
