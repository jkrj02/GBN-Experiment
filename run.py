import threading

from client import Client

if __name__ == '__main__':
    client1 = Client(1)
    client1_receiver = threading.Thread(target=client1.receive)
    client1_receiver.start()
    client1_sender = threading.Thread(target=client1.send)
    client1_sender.start()

    client2 = Client(2)
    client2_receiver = threading.Thread(target=client2.receive)
    client2_receiver.start()
    client2_sender = threading.Thread(target=client2.send)
    client2_sender.start()

    client1_receiver.join()
    client1_sender.join()
    client2_receiver.join()
    client2_sender.join()