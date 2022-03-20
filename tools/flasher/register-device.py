import machine
import binascii
import network

deviceId = binascii.hexlify(machine.unique_id()).decode()

print('{}'.format(deviceId))