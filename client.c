#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <netdb.h>
#include <pthread.h>
#include <errno.h>
#include <sys/select.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/types.h>
#include <unistd.h>

//Fases de registre
#define REG_REQ 0x00
#define REG_ACK 0x02
#define REG_NACK 0x04
#define REG_REJ 0X06
#define ERROR 0x0F
//Posibles estats del client(UDP)
#define DISCONNECTED 0xA0
#define WAIT_REG_RESPONSE 0xA2
#define WAIT_DB_CHECK 0xA4
#define REGISTERED 0XA6
#define ALIVE 0xA8
//Paquets fase de manteniment de comunicacio amb el servidor
#define ALIVE_INF 0x10
#define ALIVE_ACK 0x12
#define ALIVE_NACK 0x14
#define ALIVE_REJ 0x16
//Paquets per l'enviament de l'arxiu de cfg
#define SEND_FILE 0x20
#define SEND_DATA 0x22
#define SEND_ACK 0x24
#define SEND_NACK 0x26
#define SEND_REJ 0x28
#define SEND_END 0x2A
//Paquets per l'obtencio de l'arxiu de cfg
#define GET_FILE 0x30
#define GET_DATA 0x32
#define GET_ACK 0x34
#define GET_NACK 0x36
#define GET_REJ 0x38
#define GET_END 0x3A
//struct per els paquets UDP
struct UDP_Package {
   unsigned char tipus;
   char id_equip[7];
   char mac[13];
   char num_ale[7];
   char Dades[50];
};
//Struct per els paquets TCP
struct TCP_Package {
    unsigned char tipus;
    char id_equip[7];
    char mac[13];
    char num_ale[7];
    char Dades[150];
};
//Struct per guardar info del fitxer cfg
struct Conf {
   char id[7];
   char mac[13];
   char *nmsId;
   int nmsUdpPort;
};
//temporitzadors/llindars per les proves del protocol 
int t = 1;
int p = 2;
int q = 3;
int u = 2;
int n = 6;
int o = 2;

int r = 2;
int s = 3;
int w = 3;

//variables globals
FILE *config = NULL;
FILE *file_to_send = NULL;
int DEBUG_MODE = -1;
struct Conf device;
int UDP_sock, sock; 
struct sockaddr_in addr_server, addr_client, TCP_server, TCP_client;
struct UDP_Package client_pack, server_pack, server_data, sendAlive;
struct TCP_Package send_TCP_pack;
int failed_registers = 0;
int break_loop = -1;
int break_periodic_comm = -1;
pthread_t input_thread_id, send_alive_id;
time_t t_;
struct tm tm;
time_t now;
unsigned char STATUS = DISCONNECTED;
int sent = 0;
char *filename=NULL;
void close_sockets_and_exit();

//funcions llegir i guardar informacio del fitxer de cfg
void manage_args(int argc, char *argv[]);
void store_config();
void show_info();

//funcions per la creacio de socket i fase de registre
void UDP_socket_setup();
void register_process_loop();
void register_phase();
int register_attempt();
void UDP_server_response(int timeout);
//Funcions Comunicacio periodica i ordres de terminal
void *input();
void periodic_comunication();
void *send_alive();
int check_pack_info();
void setup_TCP_socket();
void send_TCP_package(struct TCP_Package pack);
struct TCP_Package receive_package_via_tcp_from_server(int max_timeout,int sock);
bool is_received_package_via_tcp_valid(struct TCP_Package received_package,int expected_type);
void send_file();
void get_file();
void FILE_pack();
//FUNCIONS ADICIONALS
char * get_type(int type);
void get_time();
char * get_status();
void close_sockets_and_exit();
struct timeval tcp_timeout;
int main(int argc, char *argv[]){
    signal(SIGINT, close_sockets_and_exit);
    //LLEGIR I GUARDAR INFO FIXTER CFG
    manage_args(argc,argv);
    store_config();
    show_info();
    //CREAR SOCKET I FASE DE REGISTRE
    UDP_socket_setup();
    get_time();
    printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());

    do{
        break_loop = -1;
        register_process_loop();
        /*  ATENDRE COMANDES   */
        if(break_loop == 0){
            break_periodic_comm = -1;
            break_loop = -1;
            /*FIL QUE S'ENCARREGUE DE LLEGIR LES COMANDES INTRODUIDES PER TERMINAL*/
            pthread_create(&input_thread_id, NULL, input, NULL);
            /*  COMUICACIÓ PERIÒDICA    */
            periodic_comunication();
        }
    
    } while(break_loop != 0);
    
    fclose(config);
    close_sockets_and_exit();
    exit(0);
}

void manage_args(int argc, char *argv[]){
    for(int i = 0; i < argc; i++){
        if(strcmp(argv[i], "-d") == 0){
            DEBUG_MODE = 0 ;
            printf("Executant mode debug...\n\n");
        } 
        if(strcmp(argv[i], "-c") == 0 && argc > (i + 1)){
            if(access(argv[i + 1], F_OK) != -1) {
                config = fopen(argv[i + 1], "r");
                printf("file read\n");
            } else {
                printf("Error a l'obrir el fitxer especificat\n");
                exit(-1);
            }
        }
         if(strcmp(argv[i], "-f") == 0 && argc > (i + 1)){
            if(access(argv[i + 1], F_OK) != -1) {
                file_to_send = fopen(argv[i + 1], "r");
                filename = argv[i+1];
                printf("arxiu a enviar canviat read\n");
            } else {
                printf("Error a l'obrir l'arxiu especificat\n");
                exit(-1);
            }
        }
    }

    if(config == NULL){
        if(access("client.cfg", F_OK) != -1) {
            config = fopen("client.cfg", "r");
        } else {
            printf("Error a l'obrir el fitxer predeterminat\n");
            exit(-1);
        }
    }
    if(file_to_send == NULL){
        if(access("boot.cfg", F_OK) != -1) {
            file_to_send = fopen("boot.cfg", "r");
            filename = "boot.cfg";
        } else {
            printf("Error a l'obrir l'arxiu a enviar predeterminat\n");
            exit(-1);
        }
    }
}

void store_config(){
 
   char str[50];
   const char s[4] = " ";
   char *token;
 
   while(fgets(str, 50, config)){
       str[strcspn(str, "\n")] = '\0';
       token = strtok(str, s);
       if (strcmp(token, "Id") == 0){
           token = strtok(NULL, s);
           strncpy(device.id, token, strlen(token));
       } else if (strcmp(token, "MAC") == 0){
           token = strtok(NULL, s);
           strncpy(device.mac,token, strlen(token));
       } else if (strcmp(token, "NMS-Id") == 0){
           token = strtok(NULL, s);
           device.nmsId = malloc(sizeof(token) + 1);
           strncpy(device.nmsId, token, strlen(token));
       } else if (strcmp(token, "NMS-UDP-port") == 0){
           token = strtok(NULL, s);
           device.nmsUdpPort = atoi(token);
       }
   }
}

void show_info(){
   printf("********************* DADES SOBRE EL SISTEMA DE GESTIO DE CONFIGURACIO *********************** \n");
   printf(" Identificador: %s \n", device.id);
   printf(" MAC : %s \n", device.mac);
   printf(" NMS-Id: %s \n" , device.nmsId);
   printf(" NMS-UDP-port: %d ", device.nmsUdpPort);
   printf("\n************************************************************ \n");
}

void UDP_socket_setup(){

    struct hostent *ent;
    ent = gethostbyname(device.nmsId);
    
    if(!ent){
        printf("Error al trobar %s \n", device.nmsId);
        exit(-1);
    }
    
    UDP_sock = socket(AF_INET, SOCK_DGRAM, 0);
    
    if(UDP_sock < 0){
        printf("Error en obrir el socket! \n");
        exit(-1);
    }
    
    memset(&addr_client, 0, sizeof(struct sockaddr_in));
    addr_client.sin_family=AF_INET;
    addr_client.sin_addr.s_addr=htonl(INADDR_ANY);
    addr_client.sin_port=htonl(0);
    
    if(bind(UDP_sock, (struct sockaddr*)&addr_client, sizeof(struct sockaddr_in)) < 0){
        printf("Error al connectar el socket (UDP_socket_setup)\n");
        exit(-1);
    }
    
    memset(&addr_server, 0, sizeof(struct sockaddr_in));
    addr_server.sin_family = AF_INET;
    addr_server.sin_addr.s_addr = (((struct in_addr *)ent->h_addr_list[0])->s_addr);
    addr_server.sin_port = htons(device.nmsUdpPort);
}

void register_process_loop(){
    sleep(0.5);
    /* Fase de registre, on es fa el primer intercanvi de paquets per a realitzar-lo , s'envia el primer paquet REGISTER_REQ i pasa a registerd */
    register_phase();
    while(true){

        if (server_pack.tipus == REG_ACK){
            STATUS = REGISTERED;
            break_loop = 0;
            get_time();
            printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
            server_data.tipus = server_pack.tipus;
            strcpy(server_data.num_ale, server_pack.num_ale);
            strcpy(server_data.Dades, server_pack.Dades);
            strcpy(server_data.mac, server_pack.mac);
            strcpy(server_data.id_equip, server_pack.id_equip);
            

            if(strcmp(server_pack.Dades, "EMPTY") == 0){
                STATUS = DISCONNECTED;
                get_time();
                printf("%02d:%02d:%02d  => Paquet REQUEST_ACK rebut sense dades.Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
                get_time();
                printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
                failed_registers += 1;
                break_loop = -1;
                break;
            }
            break;

        } else if (server_pack.tipus == REG_NACK){
 
            STATUS = DISCONNECTED;
            get_time();
            if(DEBUG_MODE == 0){
                printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
            }
            failed_registers++;
            register_phase();

        } else if (server_pack.tipus == REG_REJ){
            STATUS = DISCONNECTED;
            get_time();
            printf("%02d:%02d:%02d  => Dispositiu ha estat rebutjat, passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
            printf("%02d:%02d:%02d  => Motiu del rebutjament: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, server_pack.Dades);
            sleep(1);
            close_sockets_and_exit();
        } else {
            STATUS = DISCONNECTED;
            get_time();
            printf("%02d:%02d:%02d  => Paquet reubut invalid. Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
            printf("%02d:%02d:%02d  => Rebut paquet:%s\n",tm.tm_hour, tm.tm_min, tm.tm_sec, get_type(server_pack.tipus));
            sleep(1);
            failed_registers += 1;
            break;

        }
    }
    
}

void register_phase(){

    client_pack.tipus = REG_REQ;
    strcpy(client_pack.id_equip, device.id);
    strcpy(client_pack.mac, device.mac);
    strcpy(client_pack.num_ale,"000000");
    strcpy(client_pack.Dades,"\0");
        while(failed_registers < 2){
    
            get_time();
            STATUS = WAIT_REG_RESPONSE;
            printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
        
            if(register_attempt() == 0){ // s'envia el paquet REG_REQ i el servidor contesta correctament
                return;
            }
            failed_registers += 1;
        }
    
    get_time();
    printf("%02d:%02d:%02d  => S'ha excedit el nombre màxim d'intents de registre (2). \n", tm.tm_hour, tm.tm_min, tm.tm_sec);
    exit(0);
}

int register_attempt(){
   sleep(2);
   int attempts = 0;
   int timeout = t;
 
    while(true){

        addr_server.sin_port = htons(device.nmsUdpPort);
        if(DEBUG_MODE == 0){
            printf("Enviant paquet %s\n", get_type(client_pack.tipus));
        }
        int sent = sendto(UDP_sock, &client_pack, sizeof(client_pack), 0, (struct sockaddr*) &addr_server, sizeof(addr_server));
        if(sent < 0){
            printf("Error en enviar\n");
            exit(-1);
        }

        UDP_server_response(timeout); 
        if(strcmp(server_pack.Dades, "EMPTY") == 0){
            attempts += 1;
        } else {
            return 0;
        }
        if(attempts > p){
            if(timeout <  q * t){
                timeout += t;
            }
        }
    
        if(attempts >= n){
            sleep(u);
            return -1;
        }
    }
}

void UDP_server_response(int timeout){

    strcpy(server_pack.Dades, "EMPTY");
    struct  UDP_Package *recvd_pack = malloc(sizeof(struct UDP_Package));
    
    fd_set rfds;
    FD_ZERO(&rfds);
    FD_SET(UDP_sock, &rfds);
    
    struct timeval time;
    time.tv_sec = timeout;
    time.tv_usec = 0;
    
    int retl = select(UDP_sock + 1, &rfds, NULL, NULL, &time);
    
    if(retl > 0){
        if(recvfrom(UDP_sock, recvd_pack, sizeof(struct UDP_Package), 0, (struct sockaddr *) 0,(socklen_t *) 0) < 0){
            printf("%02d:%02d:%02d  => Error en rebre el paquet \n",tm.tm_hour, tm.tm_min, tm.tm_sec);
            exit(-1);
        }

        server_pack.tipus = recvd_pack->tipus;
        strcpy(server_pack.id_equip, recvd_pack->id_equip);//num aleatori
        strcpy(server_pack.Dades, recvd_pack->Dades);//PORT TCP
        strcpy(server_pack.mac, recvd_pack->mac);
        strcpy(server_pack.num_ale, recvd_pack->num_ale);
    

        if(DEBUG_MODE == 0){
            //printf("%02d:%02d:%02d  => Rebut paquet:%s amb Dades:%s, id_equip rebut:%s, mac: %s, num ale:%s\n",tm.tm_hour, tm.tm_min, tm.tm_sec,get_type(server_pack.tipus), server_pack.Dades, server_pack.id_equip, server_pack.mac,server_pack.num_ale);
        }   
    }
}

void *input(){
    
    while(true){
        char input_com[50];

        if(fgets(input_com, 50, stdin) != NULL){
            input_com[strcspn(input_com, "\n")] = '\0';
        }

        if(strcmp(input_com, "quit") == 0 && STATUS == ALIVE){
            close_sockets_and_exit();
        } else if(strcmp(input_com, "stat" ) == 0 && STATUS == ALIVE){
            show_info();
        } else {
            char * token;
            char s[2] = " ";
            token = strtok(input_com, s);

            if(token && strcmp(token, "send-cfg" ) == 0 && STATUS == ALIVE){
                if(token){
                    printf("Sending cfg file to server...\n");
                    send_file();
                } else {
                    printf("Error en la comanda send-cfg\n");
                }
                
            } else if(token && strcmp(token, "get-cfg") == 0 && STATUS == ALIVE){
                if(token){
                    printf("Getting cfg file from server...\n");
                    get_file();
                } else {
                    printf("Error en la comanda get-cfg\n");
                }
            }else{
                printf("Comanda introduida erronea\n");
            }
        } 
    }
}

void periodic_comunication(){
    /* el fil es limitarà a enviar els ALIVES al servidor */
    pthread_create(&send_alive_id, NULL, send_alive, NULL);
    /* la resta de la funció s'ocupa del seguiment dels ALIVES entrants */
    int is_first = 0;
    int alives_not_recieved = 0;
    //int is_TCP_running = -1;
    while(break_periodic_comm != 0){
 
        UDP_server_response(2*u);

        if(is_first == 0 && strcmp(server_pack.Dades, "EMPTY") == 0){
            get_time();
            printf("%02d:%02d:%02d => No s'ha rebut el primer ALIVE. Començant un nou procés de registre \n", tm.tm_hour, tm.tm_min, tm.tm_sec);
            failed_registers += 1;
            break_loop = -1;
            return;
        }

        while(strcmp(server_pack.Dades, "EMPTY") == 0 && alives_not_recieved < s){
            alives_not_recieved += 1;
            UDP_server_response(2*u);
        }

        if(alives_not_recieved >= s){
            get_time();
            printf("%02d:%02d:%02d  => S'han deixat de rebre 3 alives consecutius. Començant nou procés de registre \n", tm.tm_hour, tm.tm_min, tm.tm_sec);
            pthread_cancel(send_alive_id);
            failed_registers += 1;
            break_loop = -1;
            return;
        }
 
        if(check_pack_info() == 0){//ALIVE_ACK
            if(is_first == 0){
               get_time();
               STATUS = ALIVE;
               printf("%02d:%02d:%02d  => Dispositiu passa a l'estat: %s \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
               is_first = -1;
               /*
               if(TCP_sock_send == -1){
                   is_TCP_running = 0;
                   TCP_socket_setup();
               }*/
            }
 
        } else if(server_pack.tipus == ALIVE_REJ && STATUS == ALIVE){

            get_time();
            STATUS = DISCONNECTED;
            printf("%02d:%02d:%02d  => Rebut ALIVE_REJ. Possible suplantació d'identitat . Dispositiu passa a l'estat: %s . Reiniciant procés de registre...\n \n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_status());
            break_periodic_comm = 0;
            failed_registers += 1;
            /*close(TCP_sock_send);
            if(is_TCP_running == 0){
                close(TCP_sock_send);
            }*/
            
            pthread_cancel(send_alive_id);

        } else if (server_pack.tipus == ALIVE_NACK) {
           get_time();
           printf("%02d:%02d:%02d  =>  Paquet rebut %s. s'obviara el paquet i contara com a que el servidor no ha enviat respota\n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_type(server_pack.tipus));
           break_periodic_comm = 0;
           failed_registers += 1;
        } else {
            get_time();
            printf("%02d:%02d:%02d  =>  Paquet rebut %s. amb dades incorrectes\n", tm.tm_hour, tm.tm_min, tm.tm_sec, get_type(server_pack.tipus));
           
        }
    }    
}

void send_TCP_package(struct TCP_Package pack){
    int bytes_sent;
    
    bytes_sent = write(sock, &pack, sizeof(pack));
    if(pack.tipus == SEND_END){
        printf("%02d:%02d:%02d  => Finalitzat l'enviament d'arxiu de configuració al servidor (%s)\n",tm.tm_hour, tm.tm_min, tm.tm_sec, filename);
    }else if(pack.tipus == SEND_FILE){
        printf("%02d:%02d:%02d  => Sol·licitud d'enviament d'arxiu de configuració al servidor (%s)\n",tm.tm_hour, tm.tm_min, tm.tm_sec, filename);
    }else if(pack.tipus == SEND_DATA){
        printf("%02d:%02d:%02d  => Enviant paquet amb linea: %d de l'arxiu de configuració al servidor (%s)\n",tm.tm_hour, tm.tm_min, tm.tm_sec, sent, filename);
        sent++;
    }
    if(bytes_sent < 0){
        printf("Error en enviar paquet TCP\n");
        sleep(1);
        exit(-1);
    } else if (bytes_sent != sizeof(pack)) {
        printf("warning: only %d bytes sent instead of %lu\n", bytes_sent, sizeof(pack));
        // handle partial send
    }
    if(DEBUG_MODE == 0){
        printf("Enviat paquet tipus: %s amb elements -> id equip:%s, mac:%s, num_ale:%s, Dades:%s\n", get_type(pack.tipus),pack.id_equip, pack.mac, pack.num_ale, pack.Dades);
    }
}

void setup_TCP_socket(){
    struct hostent *ent;
    ent = gethostbyname(device.nmsId);
    if(!ent){
        printf("Error al trobar %s \n", device.nmsId);
        exit(-1);
    }
 
    sock = socket(AF_INET, SOCK_STREAM, 0);
    
    if(sock < 0){
        printf("Error en obrir el socket! \n");
        exit(-1);
    }
    
    memset(&TCP_server, 0, sizeof(struct sockaddr_in));
    TCP_server.sin_family = AF_INET;
    TCP_server.sin_addr.s_addr = (((struct in_addr *)ent->h_addr_list[0])->s_addr);
    TCP_server.sin_port = htons(atoi(server_data.Dades));
    if(connect(sock, (struct sockaddr*)&TCP_server, sizeof(struct sockaddr_in))< 0){
        printf("Error al connectar el socket (TCP_socket_setup)\n");
        exit(-1);
    }

}

void send_file(){
    setup_TCP_socket();
    FILE_pack();
    send_TCP_package(send_TCP_pack);
    struct TCP_Package received_package = receive_package_via_tcp_from_server(w,sock);
    if(received_package.tipus == SEND_ACK){
        send_TCP_pack.tipus = SEND_DATA;
        if (file_to_send == NULL) {
            printf("Error opening file.\n");
            return;
        }
        fd_set rfds;
        if(select(file_to_send, &rfds, NULL, NULL, &tcp_timeout)<0){
            printf("%02d:%02d:%02d  => Fitxer a enviar buit\n",tm.tm_hour, tm.tm_min, tm.tm_sec);
        
        }
        char line[150];
        while (fgets(line, sizeof(line), file_to_send) != NULL) {
            // Remove newline character from the end of the line
            //line[strcspn(line, "\r\n")] = '\0';

            memset(send_TCP_pack.Dades, 0, sizeof(send_TCP_pack.Dades));
            
            // Append line to the Dades member of the package object
            strcat(send_TCP_pack.Dades, line);
            send_TCP_package(send_TCP_pack);
        }
        send_TCP_pack.tipus = SEND_END;
        memset(send_TCP_pack.Dades, 0, sizeof(send_TCP_pack.Dades));
        send_TCP_package(send_TCP_pack);
        fclose(file_to_send);
    }else{
        printf("%02d:%02d:%02d  => Tancant socket TCP ja que no s'ha rebut el SEND_ACK del servidor\n",tm.tm_hour, tm.tm_min, tm.tm_sec);
        close(sock);
        fclose(file_to_send);
        close_sockets_and_exit();
        
    }
    

}

void get_file(){;
    setup_TCP_socket();
    FILE_pack(); 
    send_TCP_pack.tipus = GET_FILE;
    strcpy(send_TCP_pack.id_equip, device.id);
    strcpy(send_TCP_pack.mac, device.mac);
    strcpy(send_TCP_pack.num_ale,server_pack.num_ale);
    char result[1024];
    snprintf(result, sizeof(result), "%s", filename);
    strcpy(send_TCP_pack.Dades,result);
    send_TCP_package(send_TCP_pack);

    FILE *network_dev_config_file = fopen(filename, "w");

    struct TCP_Package received_package = receive_package_via_tcp_from_server(w,sock);
   
    while (received_package.tipus != GET_END) {
        /* receive GET_DATA packages from server, ensure they're valid and fill conf file up */
        received_package = receive_package_via_tcp_from_server(w,sock);
           if (tcp_timeout.tv_sec == 0) {
            if (DEBUG_MODE == 0) {
                char message[150];
                sprintf(message, "ERROR -> Have not received any data on TCP socket during %d seconds\n", w);
                printf("%s",message);
            }
            close(sock);
            fclose(network_dev_config_file);
            return;
        } else if (!is_received_package_via_tcp_valid(received_package, GET_DATA) && !is_received_package_via_tcp_valid(received_package, GET_END) ) {
            if (DEBUG_MODE == 0) { printf("ERROR -> Wrong package GET_DATA or GET_END received from server\n"); }
            close(sock);
            fclose(network_dev_config_file);
            return;
        }
        fputs(received_package.Dades, network_dev_config_file);
    }
    close(sock);
    fclose(network_dev_config_file);
    printf("INFO -> Successfully ended reception of configuration file from server\n");
}

bool is_received_package_via_tcp_valid(struct TCP_Package received_package,int expected_type) {
    if (expected_type == GET_END) {
        return (expected_type == received_package.tipus &&
                strcmp(server_data.id_equip, received_package.id_equip) == 0 &&
                strcmp(server_data.mac, received_package.mac) == 0 &&
                strcmp(server_data.num_ale, received_package.num_ale) == 0 &&
                strcmp("", received_package.Dades) == 0);
    }
    /* if packet's type is different than GET_END */
    return (expected_type == received_package.tipus &&
            strcmp(server_data.id_equip, received_package.id_equip) == 0 &&
            strcmp(server_data.mac, received_package.mac) == 0 &&
            strcmp(server_data.num_ale, received_package.num_ale) == 0);
}

struct TCP_Package receive_package_via_tcp_from_server(int max_timeout,int sock) {
    
    fd_set rfds;
    char *buf = malloc(sizeof(struct TCP_Package));
    struct TCP_Package *received_package = malloc(sizeof(struct TCP_Package));
    
    FD_ZERO(&rfds); /* clears set */
    FD_SET(sock, &rfds); /* add socket to descriptor set */
    tcp_timeout.tv_sec = max_timeout;
    /* if any data in socket */
    if (select(sock + 1, &rfds, NULL, NULL, &tcp_timeout) > 0) {
        read(sock, buf, sizeof(struct TCP_Package));
        received_package = (struct TCP_Package *) buf;
        if (DEBUG_MODE == 0) {
            char message[280];
            sprintf(message,
                    "DEBUG -> \t\t Received %s;\n"
                    "\t\t\t\t\t  Bytes:%lu,\n"
                    "\t\t\t\t\t  name:%s,\n " 
                    "\t\t\t\t\t  mac:%s,\n"
                    "\t\t\t\t\t  rand num:%s,\n"
                    "\t\t\t\t\t  data:%s\n\n",
                    get_type(received_package->tipus),
                    sizeof(*received_package), (*received_package).id_equip,
                    (*received_package).mac, (*received_package).num_ale,
                    (*received_package).Dades);
             printf("%02d:%02d:%02d  => %s\n",tm.tm_hour, tm.tm_min, tm.tm_sec, message);
        }
    }

    return *received_package;
}

void *send_alive(){
    addr_server.sin_port = htons(device.nmsUdpPort);
    while(true){
        sendAlive.tipus = ALIVE_INF;
        strcpy(sendAlive.id_equip, device.id);
        strcpy(sendAlive.mac, device.mac);
        strcpy(sendAlive.num_ale,server_pack.num_ale);
        //strcpy(sendAlive.Dades,"");
        
        int sent = sendto(UDP_sock, &sendAlive, sizeof(sendAlive), 0, (struct sockaddr*) &addr_server, sizeof(addr_server));
        if(sent < 0){
            printf("Error en enviar\n");
            exit(-1);
        }
        if(DEBUG_MODE == 0){
            //printf("%02d:%02d:%02d => Paquet_enviat amb id_equip:%s, Dades:%s, mac:%s, num ale:%s, tipus :%s\n",tm.tm_hour, tm.tm_min, tm.tm_sec,sendAlive.id_equip,sendAlive.Dades,sendAlive.mac,sendAlive.num_ale,get_type(sendAlive.tipus));
        }
        sleep(r);
    }
}

int check_pack_info(){
   
    if(server_pack.tipus == ALIVE_ACK && 
            (strcmp(server_pack.id_equip, server_data.id_equip) == 0) && 
            (strcmp(server_pack.mac, server_data.mac)) == 0 && 
            (strcmp(server_pack.num_ale, server_data.num_ale ) == 0)){
        return 0;
    }
    return -1;
}

char * get_type(int type){
 
   char *ret = malloc(11);
 
    if(type == REG_REQ){
        strcpy(ret, "REG_REQ");
    } else if(type == REG_ACK){
        strcpy(ret, "REG_ACK");
    } else if(type == REG_NACK){
        strcpy(ret, "REG_NACK");
    } else if(type == REG_REJ){
        strcpy(ret, "REG_REJ");
    } else if(type == ALIVE_INF){
        strcpy(ret, "ALIVE_INF");
    } else if(type == ALIVE_ACK){
        strcpy(ret, "ALIVE_ACK");
    } else if (type == ALIVE_NACK){
        strcpy(ret, "ALIVE_NACK");
    } else if (type == ALIVE_REJ){
        strcpy(ret, "ALIVE_REJ");
    } else if(type == SEND_FILE){
        strcpy(ret, "SEND_FILE");
    } else if (type == SEND_DATA){
        strcpy(ret, "SEND_DATA");
    } else if(type == SEND_ACK){
        strcpy(ret, "SEND_ACK");
    } else if(type == SEND_NACK){
        strcpy(ret, "SEND_NACK");
    } else if(type == SEND_REJ){
        strcpy(ret, "SEND_REJ");
    } else if(type == SEND_END){
        strcpy(ret, "SEND_END");
    } else if(type == GET_FILE){
        strcpy(ret, "GET_FILE");
    } else if(type == GET_DATA){
        strcpy(ret, "GET_DATA");
    } else if(type == GET_ACK){
        strcpy(ret, "GET_ACK");
    } else if(type == GET_NACK){
        strcpy(ret, "GET_NACK");
    } else if(type == GET_REJ){
        strcpy(ret, "GET_REJ");
    } else {
        strcpy(ret, "GET_END");
    }
    return ret;
}

void get_time(){
   t_ = time(NULL);
   tm = *localtime(&t_);
}

char * get_status(){
 
    char *ret = malloc(24);
 
    if(STATUS == DISCONNECTED){
        strcpy(ret, "DISCONNECTED");
        return ret;
    } else if(STATUS == WAIT_REG_RESPONSE){
        strcpy(ret, "WAIT_REG_RESPONSE");
        return ret;
    } else if(STATUS == WAIT_DB_CHECK){
        strcpy(ret, "WAIT_DB_CHECK");
        return ret;
    } else if(STATUS == REGISTERED){
        strcpy(ret, "REGISTERED");
        return ret;
    } else{
        strcpy(ret, "SEND_ALIVE");
        return ret;
    }
}

void FILE_pack(){
    /*TROBO LA LENGTH DEL FITXER EN BYTES*/
    long file_length;
    fseek(file_to_send,0,SEEK_END);
    file_length = ftell(file_to_send);
    //despres de trobar la llargada el punter del fitxer esta al final d'aquest, per tan per ara poderlo llegir desde el principi es fa un rewind
    rewind(file_to_send);
    /*Es crea el SEND_FILE*/
    send_TCP_pack.tipus = SEND_FILE;
    strcpy(send_TCP_pack.id_equip, device.id);
    strcpy(send_TCP_pack.mac, device.mac);
    strcpy(send_TCP_pack.num_ale,server_pack.num_ale);
    char result[1024];
    snprintf(result, sizeof(result), "%s,%ld", filename, file_length);
    strcpy(send_TCP_pack.Dades,result);
}

void close_sockets_and_exit(){
    printf("\nSortint de client...\n");
    close(UDP_sock);
    free(device.nmsId);
    exit(0);
}