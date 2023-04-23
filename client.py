import os
import random
import socket
import sys
import threading
import time

import configuration
import frame
import timeController


def send_check(data):
    conf = configuration.Configuration()
    rand_lost = random.randint(1, 100)
    rand_error = random.randint(1, 100)
    if rand_lost > conf.LostRate and rand_error > conf.ErrorRate:
        return data
    elif rand_lost > conf.LostRate:
        return data + b'\xff'
    else:
        return None


class Client:
    def __init__(self, client_number):
        self.is_sending = None
        conf = configuration.Configuration()
        self.client_number = client_number
        if client_number == 1:
            self.addr = ('localhost', conf.UDPPort_Client1)
            self.dest_addr_1 = ('localhost', conf.UDPPort_Client2)
            self.dest_addr_2 = ('localhost', conf.UDPPort_Client3)
        elif client_number == 2:
            self.addr = ('localhost', conf.UDPPort_Client2)
            self.dest_addr_1 = ('localhost', conf.UDPPort_Client1)
            self.dest_addr_2 = ('localhost', conf.UDPPort_Client3)
        else:
            self.addr = ('localhost', conf.UDPPort_Client3)
            self.dest_addr_1 = ('localhost', conf.UDPPort_Client1)
            self.dest_addr_2 = ('localhost', conf.UDPPort_Client2)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        self.sock.settimeout(3.0)
        self.packets = []
        self.time_list = [time.time()]
        self.time_controller = timeController.TimeController()
        self.next_to_send = 0
        self.last_ack = 0
        self.receiver_last_ack = 0
        self.log_buffer = ''
        self.send_number = 1
        self.receive_number = 1

    def send_data(self, window_size, packets_len, status):
        conf = configuration.Configuration()
        if status == 'TO':
            del(self.time_list[self.next_to_send:])
        last_ack = self.last_ack    # avoid updating while send
        while self.next_to_send <= min(last_ack + window_size, packets_len):
            frame_send = self.next_to_send % conf.SWSize
            data = frame.make(self.client_number, frame_send, self.next_to_send, self.packets[self.next_to_send - 1])
            data = send_check(data)
            if data:
                self.sock.sendto(data, self.dest_addr_1)
            self.log_buffer += ('Client {} Send: {}, pdu_to_send={}, status={}, ackedNo={}\n'
                                .format(self.client_number, self.send_number, self.next_to_send, status, last_ack))
            self.time_list.append(time.time())
            # print('Client {} Send: {}, pdu_to_send={}, status={}, ackedNo={}'
            #       .format(self.client_number, self.send_number, self.next_to_send, 'New', self.last_ack))
            self.send_number += 1
            self.next_to_send += 1

    def send(self):
        self.log_buffer += 'Sender start.\n'
        self.is_sending = 1
        conf = configuration.Configuration()

        # change file to packets
        self.packets = []
        try:
            file = open('text' + str(self.client_number) + '.txt', 'rb')
        except IOError:
            print('Unable to open text' + str(self.client_number) + '.txt')
            return

        while True:
            data = file.read(1024)
            if not data:
                break
            self.packets.append(data)
        packets_len = len(self.packets)
        window_size = min(packets_len, conf.SWSize)

        # send data
        self.next_to_send = self.last_ack + 1
        self.send_data(window_size, packets_len, 'New')
        # self.time_controller.start()
        while self.last_ack < packets_len:
            # wait
            while self.last_ack < packets_len and \
                    time.time() - self.time_list[self.last_ack + 1] <= conf.Timeout / 1000.0:
                # print(time.time() - self.time_controller.start_time)
                time.sleep(0.2)
                self.send_data(window_size, packets_len, 'New')  # if window slipped
                window_size = min(packets_len - self.last_ack, conf.SWSize)  # avoid out of range

            # time out
            if self.last_ack < packets_len:    # not finish
                self.log_buffer += ('Client {} timeout\n'.format(self.client_number))
                self.time_controller.stop()
                self.next_to_send = self.last_ack + 1
                self.send_data(window_size, packets_len, 'TO')
                window_size = min(packets_len - self.last_ack, conf.SWSize)  # avoid out of range

                # self.time_controller.start()

        # send a package to show finish
        empty_package = frame.make(0, 1, 0, b'')
        self.sock.sendto(empty_package, self.dest_addr_1)
        self.is_sending = 0
        file.close()

    def receive(self):
        self.log_buffer += 'Receiver start.\n'
        conf = configuration.Configuration()

        # open file
        try:
            file = open('receive' + str(self.client_number) + '.txt', 'wb')
        except IOError:
            print('Unable to open receive' + str(self.client_number) + '.txt')
            return

        receive_finish = False
        while True:
            if receive_finish and not self.is_sending:
                break
            # get data
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.error:
                continue
            if not data:
                file.close()
                receive_finish = True
                continue
            sender, frame_number, data_number, data, checksum = frame.extract(data)
            if self.receiver_last_ack % 100 == 0:
                print(self.client_number, self.receiver_last_ack)

            if sender == 0 and frame_number > data_number:
                # finish tag
                receive_finish = True
                continue
            elif self.is_sending and sender == 0:
                # receive ACK
                self.log_buffer += ('Client {} Receive ACK {}\n'.format(self.client_number, data_number))
                # self.time_controller.stop()
                self.last_ack = data_number  # sender last_ack
            elif data_number == self.receiver_last_ack + 1 \
                    and frame.crc_check(sender, frame_number, data_number, data, checksum):
                # correct package -> Send back an ACK
                self.log_buffer += ('Client {} Receive: {}, pdu_exp={}, pdu_recv={}, status=OK\n'
                                    .format(self.client_number, self.receive_number,
                                            str(self.receiver_last_ack + 1), str(data_number)))
                self.log_buffer += ('Client {} Send ACK\n'
                                    .format(self.client_number))
                self.receive_number += 1
                self.receiver_last_ack += 1
                ack = frame.make(0, 0, data_number)
                self.sock.sendto(ack, self.dest_addr_1)
                file.write(data)
            elif data_number == self.receiver_last_ack + 1:
                # wrong package
                self.log_buffer += ('Client {} Receive: {}, pdu_exp={}, pdu_recv={}, status=DataErr\n'
                                    .format(self.client_number, self.receive_number, self.receiver_last_ack + 1,
                                            data_number))
                self.receive_number += 1
                ack = frame.make(0, 0, self.receiver_last_ack)
                self.sock.sendto(ack, self.dest_addr_1)
            else:
                # wrong number
                self.log_buffer += ('Client {} Receive: {}, pdu_exp={}, pdu_recv={}, status=NoErr\n'
                                    .format(self.client_number, self.receive_number, self.receiver_last_ack + 1,
                                            data_number))
                self.receive_number += 1
                ack = frame.make(0, 0, self.receiver_last_ack)
                self.sock.sendto(ack, self.dest_addr_1)

        # open log file
        try:
            file = open('log{}.txt'.format(str(self.client_number)), 'w', encoding='utf-8')
        except IOError:
            print('Unable to open log document')
            return
        file.write(self.log_buffer)
        file.close()
        print('Log write finished.')

# if __name__ == '__main__':
#     client1 = Client(1)
#     client1_receiver = threading.Thread(target=client1.receive)
#     client1_receiver.start()
#     client1_sender = threading.Thread(target=client1.send)
#     client1_sender.start()
#
#     client2 = Client(2)
#     client2_receiver = threading.Thread(target=client2.receive)
#     client2_receiver.start()
#     client2_sender = threading.Thread(target=client2.send)
#     client2_sender.start()
#
#     client1_receiver.join()
#     client1_sender.join()
#     client2_receiver.join()
#     client2_sender.join()
