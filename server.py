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