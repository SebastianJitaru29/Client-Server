all:
		gcc client.c -ansi -pedantic -std=c17 -Wall -lpthread -o client
clean:
		-rm -fr client