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
from datetime import timedelta
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

J = 2
S = 3
R = 3
K = 4
clients_data_mutex = threading.Lock()
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

def construct_register_ack_package(client_random_num):
    register_ack = struct.pack('B7s13s7s50s',REG_ACK,bytes(str(servidor.id),'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(client_random_num),'utf-8'), bytes(str(sockets.tcp_port),'utf-8'))
    return register_ack

def construct_register_nack_package(reason):
    reg_nack =  struct.pack('B7s13s7s50s', REG_NACK, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(""), 'utf-8'), bytes(str(reason), 'utf-8'))
    return reg_nack

def construct_register_rej_package(reason):
    #tots els camps de la pdu amb valors a 0 i el motiu del rebuig , no estan posats a 0 perque es mes simple a l hora de debugar
    register_rej =  struct.pack('B7s13s7s50s', REG_REJ, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(""), 'utf-8'), bytes(str(reason), 'utf-8'))
    return register_rej

def construct_alive_ack_package(num_ale):
    alive_ack =  struct.pack('B7s13s7s50s', ALIVE_ACK, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(num_ale), 'utf-8'), bytes(str(""), 'utf-8'))
    return alive_ack

def construct_alive_rej_package(reason):
    alive_rej =  struct.pack('B7s13s7s50s', ALIVE_REJ, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(""), 'utf-8'), bytes(str(reason), 'utf-8'))
    return alive_rej

def construct_alive_nack_package(reason):
    alive_nack =  struct.pack('B7s13s7s50s', ALIVE_NACK, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(""), 'utf-8'), bytes(str(reason), 'utf-8'))
    return alive_nack

def construct_alive_inf_package(reason):
    alive_inf =  struct.pack('B7s13s7s50s', ALIVE_INF, bytes(str(servidor.id), 'utf-8'),bytes(str(servidor.mac),'utf-8'), bytes(str(""), 'utf-8'), bytes(str(reason), 'utf-8'))
    return alive_inf

def get_client_random_num(client_name):
    for valid_client in authorized_clients:
        if valid_client.id_equip == client_name:
            return valid_client.num_ale
    return None 

def change_client_state(id_equip, new_state):
    for valid_client in authorized_clients:
        if valid_client.id_equip == id_equip:
            if valid_client.state != new_state:
                valid_client.state = new_state
                if new_state == "REGISTERED" and debug_mode:
                    print("INFO  -> Client: " + valid_client.id_equip +
                                  " successfully signed up on server; " +
                                  " ip: " + valid_client.ip_address + " mac: " +
                                  valid_client.mac + " rand_num: " +
                                  str(valid_client.num_ale))
                print("INFO  -> Client " + id_equip + " changed its state to: "
                              + get_status(new_state))
            else:
                if new_state == "REGISTERED" and debug_mode:
                    print("DEBUG -> Client 'changed' its state to REGISTERED "
                                  "(Duplicated signup)")

def get_client_from_list(client_name):
    for valid_client in authorized_clients:
        if valid_client.id_equip == client_name:
            return valid_client
    return None

def are_name_and_mac_valid(client_id_equip, client_mac_address):
    for valid_client in authorized_clients:
        if str(valid_client.id_equip) == client_id_equip:
            if valid_client.mac == client_mac_address:
                return True
            break
    return False

def are_random_num_and_ip_address_valid(client_name, to_check_random_num, to_check_ip_address):
    for valid_client in authorized_clients:
        if valid_client.id_equip == client_name:
            return valid_client.ip_address == to_check_ip_address and \
                   valid_client.num_ale == to_check_random_num
    return False

def are_random_num_and_ip_address_valid(client_name, to_check_random_num, to_check_ip_address):
    for valid_client in authorized_clients:
        if valid_client.id_equip == client_name:
            return valid_client.ip_address == to_check_ip_address and \
                   valid_client.num_ale == to_check_random_num
    return False

def get_client_from_udp_port_and_ip(udp_port, ip_address):
    for valid_client in authorized_clients:
        if udp_port == valid_client.udp_port and ip_address == valid_client.ip_address:
            return valid_client
    return None

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

def is_authorized(id_equip,mac):
    for client in authorized_clients:
        if client.id_equip == id_equip and client.mac == mac:
            return True
        
def send_package_via_udp_to_client(package_to_send, to_udp_port, to_ip_address):
    sockets.udp_socket.sendto(package_to_send, (to_ip_address, to_udp_port))
    package_to_send_unpacked = struct.unpack('B7s13s7s50s', package_to_send)
    if debug_mode:
        current_time = time.strftime("%H:%M:%S", time.localtime(time.time()))
        print("DEBUG "+ str(current_time)+ "-> Sent " + convert_type_to_string(package_to_send_unpacked[0])
                      + ";\n" + "\t Bytes: " + str(struct.calcsize('B7s13s7s50s')) + ",\n" +
                      "\t name: " + package_to_send_unpacked[1].split(b"\x00")[0].decode("utf-8") + ",\n" +
                      "\t mac: " + package_to_send_unpacked[2].split(b"\x00")[0].decode("utf-8") + ",\n" +
                      "\t rand num: " + package_to_send_unpacked[3].split(b"\x00")[0].decode("utf-8") + ",\n" +
                      "\t data: " + package_to_send_unpacked[4].split(b"\x00")[0].decode("utf-8") + "\n")

def recive_package_from_udp():
    received_package_packed, (client_ip_address, client_udp_port) = sockets.udp_socket.\
                                                                    recvfrom(84)
    received_package_unpacked = struct.unpack('B7s13s7s50s', received_package_packed)
    package_type = received_package_unpacked[0]
    client_id_equip = received_package_unpacked[1].split(b"\x00")[0].decode("utf-8")
    client_mac = received_package_unpacked[2].split(b"\x00")[0].decode("utf-8")
    num_ale = received_package_unpacked[3].split(b"\x00")[0].decode("utf-8")
    dades = received_package_unpacked[4].split(b"\x00")[0].decode("utf-8")

    if debug_mode == True:
           current_time = time.strftime("%H:%M:%S", time.localtime(time.time()))
           print("DEBUG" + str(current_time)+"-> Received " + convert_type_to_string(package_type) +
                      "; \n" + "\t  Bytes: " + str(84) + ", \n" +
                      "\t  name: " + client_id_equip + ", \n" +
                      "\t  mac: " + client_mac + ", \n" +
                      "\t  rand num: " + num_ale + ", \n" +
                      "\t  data: " + dades + "\n")
    return client_ip_address,client_udp_port,package_type,client_id_equip,client_mac,num_ale,dades

def keep_in_touch_with_client(client, first_alive_inf_timeout):
    """
    Makes sure client stays in touch with server using udp socket by checking whether
    client.is_alive_received is True before a countdown.
    client.is_alive_received is changed to True on serve_alive_inf function when
    receiving an ALIVE_INF pdu and then changed to False inside this function.
    :param client: client that must keep in touch
    :param first_alive_inf_timeout: maximum datetime to receive first alive_inf
    """

    while True:
        try:
            if client.state == REGISTERED:
                is_first_alive_received = False
                while datetime.now() < first_alive_inf_timeout:
                    if client.is_alive_received:
                        is_first_alive_received = True
                        clients_data_mutex.acquire()
                        client.is_alive_received = False
                        clients_data_mutex.release()
                    time.sleep(0.01)
                if not is_first_alive_received:
                    print("INFO  -> Have not received first ALIVE_INF in "
                                  + str(J * R) + " seconds")
                    clients_data_mutex.acquire()
                    change_client_state(client.id_equip, DISCONNECTED)
                    clients_data_mutex.release()
                    return

            elif client.state == ALIVE:
                alive_inf_timeout = datetime.now() + timedelta(seconds=R)
                is_alive_received = False
                while datetime.now() < alive_inf_timeout:
                    if client.is_alive_received:
                        clients_data_mutex.acquire()
                        client.consecutive_non_received_alives = 0
                        client.is_alive_received = False
                        clients_data_mutex.release()
                    time.sleep(0.01)
                if not is_alive_received:
                    clients_data_mutex.acquire()
                    client.consecutive_non_received_alives += 1
                    if client.consecutive_non_received_alives == K:
                        print("INFO  -> Have not received " + str(K) +
                                      " consecutive ALIVES")
                        change_client_state(client.id_equip, DISCONNECTED)
                        client.consecutive_non_received_alives = 0
                        clients_data_mutex.release()
                        return
                    clients_data_mutex.release()
        # datetime.now() is None when main thread exits, so could throw AttributeError
        except AttributeError:
            return

def serve_client_register_via_udp(client,dades):

    change_client_state(client.id_equip,WAIT_DB_CHECK)

    if not is_authorized(client.id_equip,client.mac): 
        if debug_mode == True:
            print("Rebut paquet REG_REQ; informació incorrecta o client no autoritzat. S'envia REG_REJ")
        #generar paquet REG_REJ
        REG_REJ_package =construct_register_rej_package("Client no autoritzat")
        send_package_via_udp_to_client(REG_REJ_package, client.udp_port, client.ip_address)
        change_client_state(client.id_equip, DISCONNECTED)
        return
    if client.state == WAIT_DB_CHECK:
        if client.num_ale != "000000":
            if debug_mode:
                print("Rebuda peticio de registre amb numero aleatori incorrecte, hauria de ser :000000 ")
            register_nack_package = construct_register_nack_package("wrong data recieved")
            send_package_via_udp_to_client(register_nack_package,client.udp_port,client.ip_address)
            return
        change_client_state(client.id_equip,REGISTERED)
        
        alive_inf_timeout = datetime.now() + timedelta(seconds=(J*R))
        REG_ACK_package = construct_register_ack_package(get_client_random_num(client.id_equip))
        send_package_via_udp_to_client(REG_ACK_package, client.udp_port, client.ip_address)
    
        keep_in_touch_with_client(client,alive_inf_timeout)

    if client.state == REGISTERED or client.state == ALIVE:
        if not are_random_num_and_ip_address_valid(client.id_equip,client.num_ale, client.ip_address):
            register_nack_package = construct_alive_nack_package("wrong data recieved")
            send_package_via_udp_to_client(register_nack_package,client.udp_port,client.ip_adress)
            return
    clients_data_mutex.acquire()
    change_client_state(client.id_equip, REGISTERED)
    clients_data_mutex.release()
    register_ack_package  = construct_register_ack_package(get_client_random_num(client.id_equip))
    send_package_via_udp_to_client(register_ack_package,client.udp_port,client.ip_address)

def serve_alive_inf(client,dades):

    client1 = get_client_from_udp_port_and_ip(client.udp_port,client.ip_address)
    
    if client1 is not None:
        client1.is_alive_recieved = True
    clients_data_mutex.acquire()

    if not are_name_and_mac_valid(client.id_equip, client.mac):
        if debug_mode:
            print("ALIVE_INF recieved from invalid user:" + client.id_equip + "ip:" + client.ip_address + "mac:" + client.mac)
        clients_data_mutex
        alive_rej_package = construct_alive_rej_package("User not allowed")
        send_package_via_udp_to_client(alive_rej_package,client.udp_port,client.ip_address)
        return
    elif not are_random_num_and_ip_address_valid(client.id_equip,client.num_ale,client.ip_address):
        if debug_mode:
            print("Wrong num_ale in the ALIVE_INF package")
        clients_data_mutex.release()
        alive_nack_package = construct_alive_nack_package("Wrong data recieved, wrong number")
        send_package_via_udp_to_client(alive_nack_package,client.udp_port,client.ip_address)
        return
    else:
        change_client_state(client.id_equip, ALIVE)
        clients_data_mutex.release()
        alive_ack_package = construct_alive_ack_package(client.num_ale)
        send_package_via_udp_to_client(alive_ack_package,client.udp_port,client.ip_address)

def udp_conection(client, package_type, dades):
    if package_type == REG_REQ:
        serve_client_register_via_udp(client,dades)
    elif package_type == ALIVE_INF:
        serve_alive_inf(client,dades)

def udp_service_loop():
    """
    Waits for udp connection,
    when getting connection creates a thread (daemon) to serve it and
    keeps waiting for incoming connections on udp socket
    """
    if debug_mode:
        print("DEBUG -> UDP socket enabled")

    while True:
        clients_data_mutex.acquire()
        client_ip_address, client_udp_port, package_type, client_id_equip, client_mac, num_ale, dades = recive_package_from_udp()
        client = get_client_from_list(client_id_equip)
        client.ip_address = client_ip_address
        client.udp_port = client_udp_port
        client.mac = client_mac
        client.num_ale = num_ale
        clients_data_mutex.release()
        thread_to_serve_udp_connection = threading.Thread(target=udp_conection,args=(client, package_type, dades))
        thread_to_serve_udp_connection.daemon = True
        thread_to_serve_udp_connection.start()

def tcp_service_loop():
    return

def service():
    """
    initiates udp and tcp service loops:
    creates a thread (daemon) to initiate tcp loop
    and then initiates udp service loop
    """
    thread_for_tcp = threading.Thread(target=tcp_service_loop)
    thread_for_tcp.daemon = True
    thread_for_tcp.start()
    
    udp_service_loop()

if __name__ == '__main__':
    try:
        manage_args(sys.argv)
        setup_UDP_socket()
        setup_TCP_socket()
        
        global input_thread
        input_thread = threading.Thread(target=terminal_input, daemon=True)
        input_thread.start()

        service()

    except(KeyboardInterrupt, SystemExit):
        print("Sortint del servidor...")
        if 'UDP_socket' in globals():
            sockets.udp_socket.close()
        if 'TCP_socket' in globals():
            sockets.tcp_socket.close()
        sys.exit()
