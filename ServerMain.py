import socket
import threading
from collections import defaultdict
from threading import Timer
import time
import random
from struct import pack
from concurrent.futures import ThreadPoolExecutor
from Colors import Colors
from TriviaQuestionManager import TriviaQuestionManager

class ServerMain:
    def __init__(self, port=13117):
        self.udp_broadcast_port = port
        self.clients = {}  # Stores client address and name
        self.trivia_manager = TriviaQuestionManager()
        self.tcp_port = random.randint(1024, 65535)
        base_server_name = "Team Mystic"
        self.server_name = base_server_name.ljust(32)
        self.broadcasting = True  # New attribute to control broadcasting
        self.game_active = False
        self.player_names_server = []
        self.add_number = list(range(1, 501))
        self.executor = ThreadPoolExecutor(max_workers=30)  # Adjust based on expected load
        self.player_names_server_lock = threading.Lock()  # Add a lock for synchronizing access
        self.game_stats = defaultdict(list)  # Tracks scores for each game
        self.player_scores = defaultdict(int)  # Tracks overall scores for each player
        self.game_count = 0
        self.server_running = True
        self.tcp_socket_server = None



    def start_udp_broadcast(self):
        """Modified to continuously broadcast using the current TCP port."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as udp_socket:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            while self.server_running:
                # Repack the message with the current TCP port
                message = pack('!Ib32sH', 0xabcddcba, 0x2, self.server_name.encode('utf-8'), self.tcp_port)
                udp_socket.sendto(message, ('<broadcast>', self.udp_broadcast_port))
                time.sleep(2)
    def accept_tcp_connections(self):
        """Accepts TCP connections from clients using a ThreadPoolExecutor."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            self.tcp_socket_server = tcp_socket
            bound = False
            attempts = 0
            while not bound and attempts < 50:
                try:
                    tcp_socket.bind(('', self.tcp_port))
                    tcp_socket.listen()
                    print(f"{Colors.GREEN}Server started, listening on IP address {socket.gethostbyname(socket.gethostname())}")
                    bound = True
                except socket.error as e:
                    print(f"{Colors.YELLOW}Port {self.tcp_port} is in use or cannot be bound. Trying another port...")

                    self.tcp_port = random.randint(1024, 65535)
                    attempts += 1

            if not bound:

                print(f"{Colors.RED}Failed to bind to a port after several attempts. Exiting.")


                return

            self.wait_for_first_connection(tcp_socket)

    def wait_for_first_connection(self, tcp_socket):
        """Waits for the first connection and starts a timer for accepting more connections."""
        first_client_connected = False

        def stop_accepting_new_connections():
            self.game_active = True
            self.manage_game_rounds()

        while not self.game_active:
            tcp_socket.settimeout(1)  # Short timeout to periodically check if game has started
            while self.server_running:
                try:
                    client_socket, addr = tcp_socket.accept()
                    self.executor.submit(self.handle_client, client_socket, addr)
                    if not first_client_connected:
                        first_client_connected = True
                        Timer(10.0, stop_accepting_new_connections).start()
                except socket.timeout:
                    continue

    def handle_client(self, client_socket, addr):
        """Handles communication with a connected client."""
        try:
            player_name = client_socket.recv(1024).decode().strip()
            with self.player_names_server_lock:  # Use the lock when accessing the shared resource
                if not self.check_name_unique(player_name):
                    player_name = player_name + str(self.add_number[0])
                    self.add_number = self.add_number[1:]
                    self.clients[addr] = (player_name, client_socket)
                    self.player_names_server.append(player_name)
                self.clients[addr] = (player_name, client_socket)
                self.player_names_server.append(player_name)

        except Exception as e:
            print(f"{Colors.RED}Failed to handle client {addr}: {e}")





    def check_name_unique(self, name):
        """Checks if the received name is unique."""
        if name not in self.player_names_server:
            return True
        return False


    def manage_game_rounds(self):
        """Manages the game rounds, ensuring the game continues until there is only one winner."""
        active_players = self.clients.copy()  # Copy the current clients as active players for this round

        round_number = 1

        while len(active_players) >= 1:
            question, correct_answer = self.trivia_manager.get_random_question()
            question =f'{Colors.BOLD}True or false:{question}{Colors.END}\n'

            if round_number == 1:
                message = f"\n{Colors.PASTEL_PEACH}Welcome to the Mystic server, where we are answering trivia questions about the Bible.\n"
                for idx, player_name in enumerate(self.clients.values(), start=1):

                    message += f"Player {idx}: {player_name[0]}\n"
                message += "==\n"+ question

            else:
                players_names = list(active_players.values())
                players_names = [name for name, _ in players_names]
                if len(players_names) > 1:
                    players_list = ', '.join(players_names[:-1]) + ' and ' + players_names[-1]
                else:
                    players_list = players_names[0]
                message = f"{Colors.PASTEL_PEACH}{Colors.UNDERLINE}Round {round_number}, played by {players_list}:\n{Colors.END}{Colors.PASTEL_PEACH}{question}"

            self.broadcast_question(active_players, message)

            # Collect and evaluate answers within a timeout (10 seconds)
            answers = self.collect_answers(active_players)
            winners, active_players = self.evaluate_answers(answers, active_players, correct_answer)

            if len(active_players) == 1 and len(winners) == 0:
                round_number += 1
            elif len(active_players) > 1 and len(winners) != 1:
                round_number += 1
            else:
                break  # Exit loop if one player is left

        if active_players:
            self.announce_winner(active_players.keys())  # Announce to all clients
        else:
            no_winners_message = f"{Colors.BOLD}\nGame over!\nNo winners"
            for addr, (_, client_socket) in self.clients.items():
                try:
                    client_socket.sendall(no_winners_message.encode('utf-8'))
                except Exception as e:

                    print(f"{Colors.RED}Failed to announce there are no winners to {self.clients[addr][0]}: {e}")

        self.game_over()

    def broadcast_question(self, active_players, message):
        """Sends the trivia question to all active players."""
        for addr, (player_name, client_socket) in active_players.items():
            try:
                client_socket.sendall(message.encode('utf-8'))
            except Exception as e:

                print(f"{Colors.RED}Error broadcasting question to player {player_name} at {addr}: {e}")

    def collect_answers(self, active_players):
        """Collects answers from each active player within a specified timeout."""
        answers = {}
        for addr, (player_name, client_socket) in active_players.items():
            try:
                data = client_socket.recv(1024).decode('utf-8').strip().upper()
                if data in ['Y', 'T', '1']:  # Interpreted as True
                    answers[addr] = True
                elif data in ['N', 'F', '0']:  # Interpreted as False
                    answers[addr] = False
                else:
                    answers[addr] = None
            except Exception as e:

                print(f"{Colors.RED}Failed to receive answer from {player_name}:{e}")


        return answers

    def evaluate_answers(self, answers, active_players, correct_answer):
        """Evaluates the collected answers and updates the list of active players, with specific output formatting."""
        winners = []
        no_correct_answers = []
        result_messages = {}
        current_game_scores = defaultdict(int)

        # First, compile the correctness of each answer
        for addr, answer in answers.items():
            player_name = active_players[addr][0]
            if correct_answer == answer:
                winners.append(addr)
                current_game_scores[player_name] += 1  # Award point for correct answer
                self.player_scores[player_name] += 1  # Update overall score
                result_messages[addr] = f"{Colors.PASTEL_ORANGE}{player_name} is correct!{Colors.END}"
            elif answer is None:
                no_correct_answers.append(addr)
                result_messages[addr] = f"{Colors.END}{Colors.PASTEL_ORANGE}{player_name} did not respond on time!{Colors.END}"
            else:
                no_correct_answers.append(addr)
                result_messages[addr] = f"{Colors.PASTEL_ORANGE}{player_name} is incorrect!{Colors.END}"

        if len(winners) == 1:
            winner_addr = winners[0]
            winner_name = active_players[winner_addr][0]
            # Add a winning note to the winner's message
            result_messages[winner_addr] += f" {Colors.PASTEL_ORANGE}{winner_name} Wins!{Colors.END}"

        # Compile the broadcast message from individual messages
        broadcast_message = "\n"+"\n".join(result_messages.values())+"\n"

        if len(no_correct_answers) != len(active_players):
            # Remove players who answered incorrectly from active_players for the next round
            for addr in list(active_players.keys()):  # Convert to list to avoid 'dictionary changed size during iteration' error
                if addr not in winners:
                    del active_players[addr]

        # Broadcast the message to all remaining players
        for addr in self.clients.keys():
            try:
                client_socket = self.clients[addr][1]
                client_socket.sendall(broadcast_message.encode('utf-8'))
            except Exception as e:
                print(f"{Colors.RED}Failed to send result message: {self.clients[addr][0]} {e}")


        self.game_stats[self.game_count].append(current_game_scores)

        return winners, active_players



    def announce_winner(self, winner_addr):
        winner_addr_tuple = list(winner_addr)[0]
        """Announces the winner to all clients."""
        winner_name, _ = self.clients[winner_addr_tuple]


        winner_message = f"{Colors.PASTEL_BLUE}{Colors.BOLD}Game over!\nCongratulations to the winner: {winner_name}"


        for addr, (_, client_socket) in self.clients.items():
            try:
                client_socket.sendall(winner_message.encode('utf-8'))
            except Exception as e:

                print(f"{Colors.RED}Failed to announce winner to {self.clients[addr][0]}: {e}")

    def game_over(self):
        """Handles tasks after a game round ends."""
        self.game_count += 1
        self.print_statistics()  # Print statistics at the end of each game

        print(f"{Colors.BLUE}Game over, sending out offer requests...")

        # Close all client connections
        for addr, (_, client_socket) in self.clients.items():
            client_socket.close()
        self.clients.clear()  # Clear the list of clients for the next round
        self.player_names_server.clear()
        self.game_active = False
        self.broadcasting = True  # Enable broadcasting for the next round
        # Optionally, restart the UDP broadcast on a new thread if not automatically restarting
        self.add_number = list(range(1, 501))
        self.start()

    def print_statistics(self):
        print(f"{Colors.END}Game Statistics:")
        print(f"Total games played: {self.game_count}")
        # Find the best player ever
        # Get the highest score or 0 if no scores are available or if all scores are less than 0
        best_score = max(0, max(self.player_scores.values(), default=0))

        # Now, find the player with this score
        best_player = next((player for player, score in self.player_scores.items() if score == best_score), "No player")
        print(f"Best player ever: {best_player} with score {self.player_scores[best_player]}")
        # Average rounds per game
        avg_rounds = int(sum(len(game) for game in self.game_stats.values()) / len(self.game_stats))
        print(f"Average rounds per game: {avg_rounds}")
        # Ranking of players by score in the latest game

        if self.game_stats:
            latest_game = self.game_stats[self.game_count - 1]  # This is a list of defaultdict(int)

            # Aggregate scores across all rounds in the latest game
            total_scores = defaultdict(int)
            for round_scores in latest_game:
                for player, score in round_scores.items():
                    total_scores[player] += score

            # Now sort the aggregated scores
            sorted_players = sorted(total_scores.items(), key=lambda item: item[1], reverse=True)

            print("Ranking players by correct answers in this game:")
            for rank, (player, score) in enumerate(sorted_players, 1):
                print(f"{rank}. {player} - {score} correct answers")

    def start(self):
        """Starts the server."""
        threading.Thread(target=self.accept_tcp_connections, daemon=True).start()
        self.start_udp_broadcast()

    def shutdown_server(self):
        """Shuts down the server and closes all active connections."""
        self.server_running = False
        self.game_active = False  # Stop the game

        # Close all client sockets
        for _, (player_name, client_socket) in self.clients.items():
            print(f"Closing connection for {player_name}")

            client_socket.close()

        # Close the server socket
        if self.tcp_socket_server:
            print(f"{Colors.BLUE}Closing the server socket...{Colors.END}")
            self.tcp_socket_server.close()

        # Clear the clients dictionary
        self.clients.clear()

        # Shutdown the thread pool executor
        self.executor.shutdown(wait=True)
        print(f"{Colors.BLUE}Server has been shutdown cleanly.{Colors.END}")


# Starting the server
if __name__ == "__main__":
    server = ServerMain()
    try:
        server.start()
    except KeyboardInterrupt:
        server.shutdown_server()