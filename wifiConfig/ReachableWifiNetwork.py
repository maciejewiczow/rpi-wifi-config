import binascii

wifiSecurityLevelNames = {
    0b000: 'Open',
    0b001: 'WEP-PSK',
    0b010: 'WPA',
    0b011: 'WPA-PSK',
    0b100: 'WPA2',
    0b101: 'WPA2-PSK',
    0b110: 'WPA/WPA2',
    0b111: 'WPA/WPA2-PSK',
}

class ReachableWifiNetwork:
    ssid: str
    bssid: str
    channel: int
    signalStrength: int
    security: str

    def __init__(self, data) -> None:
        # two last values are broken on the Pico W and mean something differend than the documentation says
        ssidBytes, bssidBytes, channel, signal, security, _ = data

        self.ssid = ssidBytes.decode()
        self.bssid = binascii.hexlify(bssidBytes).decode()
        self.channel = channel
        self.security = wifiSecurityLevelNames[security]
        self.signalStrength = signal
