import machine
import binascii
import network

deviceId = binascii.hexlify(machine.unique_id()).decode()
macId = binascii.hexlify(network.WLAN().config('mac')).decode()

print('{},{}'.format(deviceId, macId))