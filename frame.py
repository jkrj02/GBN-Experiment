def crc_make(data):
    # CCITT CRC-16: x^16 + x^12 + x^5 + 1 (0x1021)
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc <<= 1
    return crc


def crc_check(client_number, frame_number, data_number, data, checksum):
    client_number_bytes = client_number.to_bytes(1, byteorder='big', signed=False)
    frame_number_bytes = frame_number.to_bytes(1, byteorder='big', signed=False)
    data_number_bytes = data_number.to_bytes(4, byteorder='big', signed=False)
    correct_checksum = crc_make(client_number_bytes + frame_number_bytes + data_number_bytes + data)
    return correct_checksum == checksum


def make(client_number, frame_number=0, data_number=0, data=b''):
    client_number_bytes = client_number.to_bytes(1, byteorder='big', signed=False)
    frame_number_bytes = frame_number.to_bytes(1, byteorder='big', signed=False)
    data_number_bytes = data_number.to_bytes(4, byteorder='big', signed=False)
    checksum = crc_make(client_number_bytes + frame_number_bytes + data_number_bytes + data)
    checksum = checksum.to_bytes(2, byteorder='big', signed=False)
    return client_number_bytes + frame_number_bytes + data_number_bytes + data + checksum


def extract(packet):
    client_number = packet[0]
    frame_number = packet[1]
    data_number = int.from_bytes(packet[2:6], byteorder='big', signed=False)
    data = packet[6:-2]
    checksum = int.from_bytes(packet[-2:], byteorder='big', signed=False)
    return client_number, frame_number, data_number, data, checksum
