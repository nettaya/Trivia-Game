import socket
import select
import struct
import random
import time
import subprocess
import os
import platform
from inputimeout import inputimeout, TimeoutOccurred
from Colors import Colors


class ClientMain:
    """
    The ClientMain class is responsible for managing the client-side operations of a trivia game.
    It handles the network interactions, connects to the server via UDP for game initiation, and then
    uses TCP for game play. This class also deals with receiving questions, sending answers, and processing
    game rounds.

    Attributes:
        player_names (list of str): A pre-defined list of possible player names to be used for the game.
        name (str): The selected name for this client session.
        server_ip (str): The IP address of the server obtained from the UDP broadcast.
        server_port (int): The TCP port number of the server for game communication.
        tcp_socket (socket.socket): The TCP socket used for sending and receiving data during the game.
    """

    def _init_(self):
        """
        Initializes a new client session. Sets up the list of potential player names and resets
        connection details.
        """
        self.player_names = ["Aaron", "Abel", "Abraham", "Adam", "Amos", "Asher", "Barak", "Barnabas", "Bartholomew",
                             "Benjamin",
                             "Boaz", "Caleb", "Cyrus", "Dan", "Daniel", "David", "Dathan", "Eleazar", "Elijah",
                             "Elisha",
                             "Enoch", "Ephraim", "Esau", "Ethan", "Ezekiel", "Ezra", "Gad", "Gideon", "Hagar", "Haman",
                             "Hamor", "Hanan", "Hananiah", "Haniel", "Haran", "Heber", "Hezekiah", "Hiram", "Hosea",
                             "Isaac",
                             "Isaiah", "Ishmael", "Israel", "Jacob", "Jair", "James", "Japheth", "Jared", "Jason",
                             "Javan",
                             "Jedediah", "Jehoshaphat", "Jephthah", "Jeremiah", "Jesse", "Jesus", "Joel", "John",
                             "Jonah",
                             "Jonathan",
                             "Joram", "Jordan", "Joseph", "Joshua", "Josiah", "Jotham", "Judah", "Jude", "Kaleb",
                             "Kedar",
                             "Kenan", "Laban", "Lamech", "Lazarus", "Leah", "Levi", "Lot", "Luke", "Malachi",
                             "Manasseh",
                             "Mark", "Matthew", "Matthias", "Melchizedek", "Meshach", "Methuselah", "Micah", "Michael",
                             "Mordecai", "Moses",
                             "Nahum", "Naphtali", "Nathan", "Nathanael", "Nehemiah", "Nicodemus", "Noah", "Obadiah",
                             "Obed",
                             "Onan",
                             "Paul", "Peter", "Philemon", "Philip", "Phinehas", "Reuben", "Reuel", "Rufus", "Samson",
                             "Samuel",
                             "Saul", "Seraiah", "Seth", "Shadrach", "Shamgar", "Shem", "Silas", "Simeon", "Simon",
                             "Solomon",
                             "Stephen", "Tamar", "Thaddeus", "Thomas", "Timothy", "Titus", "Tobias", "Uzziah",
                             "Zachariah",
                             "Zadok",
                             "Zebulun", "Zechariah", "Zedekiah", "Zephaniah", "Zerubbabel", "Abigail", "Deborah",
                             "Delilah",
                             "Dinah", "Elizabeth",
                             "Esther", "Eve", "Hagar", "Hannah", "Huldah", "Jael", "Jezebel", "Joanna", "Judith",
                             "Leah",
                             "Lydia", "Martha", "Mary", "Miriam", "Naomi", "Rachel", "Rebekah", "Ruth", "Sarah",
                             "Susanna",
                             "Tabitha", "Zilpah", "Zipporah", "Job", "Jabez", "Jethro", "Joab", "Joash", "Joktan",
                             "Jonah",
                             "Joseph of Arimathea", "Josiah", "Jotham", "Lazerus", "Lemuel", "Mahalalel", "Malchus",
                             "Manoah", "Mathusala", "Mattaniah", "Mordecai", "Nahor", "Nekoda", "Nimrod", "Othniel",
                             "Pekah",
                             "Peleg", "Perez", "Pontius", "Ram",
                             "Seth", "Shem", "Silvanus", "Sisera", "Tertius", "Uriah", "Uzzah", "Zacchaeus", "Zedekiah",
                             "Zophar"]
        self.name = None
        self.server_ip = None
        self.server_port = None
        self.tcp_socket = None

    def listen_for_udp_broadcast(self):
        """
        Listens for UDP broadcasts from the server. This method captures the server's IP and TCP port
        from the broadcasted messages, which indicate where the server is listening for incoming TCP
        connections.
        """
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Attempt to set SO_REUSEPORT for compatibility with multiple clients on the same host
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except AttributeError:
            print(
                f"{Colors.RED}SO_REUSEADDR is not supported on this platform. Continuing with SO_REUSEADDR only.{Colors.END}")

        udp_socket.bind(('', 13117))  # Assuming 13117 is the broadcast port
        print(f"{Colors.PASTEL_GREEN}Client started, listening for offer requests...")

        while True:
            data, addr = udp_socket.recvfrom(1024)
            magic_cookie, message_type = struct.unpack('!Ib', data[:5])
            # Directly extract the server port from the correct position
            server_port = struct.unpack('!H', data[-2:])[0]  # Extract the last 2 bytes for the server port
            if magic_cookie == 0xabcddcba and message_type == 0x2:
                self.server_ip = addr[0]
                self.server_port = server_port
                print(f"Received offer from server Mystic at address {self.server_ip}, attempting to connect...")

                udp_socket.close()
                break

    def connect_to_server(self):
        """
        Establishes a TCP connection to the server using the IP and port number obtained from the
        UDP broadcast. Sends the client's player name to the server upon connection.
        """
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.connect((self.server_ip, self.server_port))
        try:
            self.tcp_socket.sendall((self.name + '\n').encode())
        except Exception as e:
            print(f"{Colors.RED}Error communicating with server: {e}{Colors.END}")

    def game_mode(self):
        """
        Handles the game mode interactions. Receives game questions and sends answers within the
        stipulated time. This function processes all incoming messages during the game and ensures
        timely responses to maintain the game flow.
        """
        try:
            game_over_received = False
            while not game_over_received:
                readable, _, _ = select.select([self.tcp_socket], [], [], None)
                if self.tcp_socket in readable:
                    # self.send_heartbeat()
                    message = self.tcp_socket.recv(1024).decode().strip()

                    if message != '':
                        print(f"\n{message}")
                        if "you did not respond in time!" in message:
                            continue
                        if "Game over!" in message:
                            game_over_received = True  # Set flag to indicate game over message received
                            break
                        if "True or false" in message:
                            # Provide a prompt for the user to input their answer within 10 seconds
                            answer = 'no answer'
                            try:
                                answer = inputimeout("Your answer (Y/1/T - for True || N/0/F - for False): ",
                                                     timeout=10).strip().upper()
                                if answer in ['Y', '1', 'T', 'N', '0', 'F']:
                                    pass
                                else:
                                    print(
                                        f"{Colors.YELLOW}Invalid input. Please insert Y/1/T - for True || N/0/F - for False")

                            except Exception as e:
                                answer = 'no answer'
                            finally:
                                # self.send_heartbeat()
                                self.tcp_socket.sendall(answer.encode())
                    else:
                        self.tcp_socket.close()
                        self.listen_for_udp_broadcast()

        except Exception as e:
            print(f"{Colors.RED}An error occurred: {e}{Colors.END}")

        finally:
            print(f"{Colors.BOLD}Server disconnected, listening for offer requests...\n")
            self.tcp_socket.close()
            self.listen_for_udp_broadcast()

    def run(self):
        """
        Runs the client session. This method is the entry point for the client logic, orchestrating the
        sequence of operations to connect to the server, participate in the game, and handle reconnections
        if necessary.
        """
        while True:
            time.sleep(1)
            try:
                self.name = random.choice(self.player_names)
                self.listen_for_udp_broadcast()
                self.connect_to_server()
                self.game_mode()
            except Exception as e:
                print(f"{Colors.RED}Error encountered: {e}. Attempting to reconnect...{Colors.END}")

                if self.tcp_socket:
                    self.tcp_socket.close()  # Ensure the socket is closed before retrying
                time.sleep(2)


if _name_ == "_main_":
    client = ClientMain()
    client.run()
