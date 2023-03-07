class SavedWifiNetwork:
    def __init__(self, ssid: str, password = None, isLastUsed = False):
        self.ssid = ssid
        self.password = password
        self.isLastUsed = isLastUsed

    @property
    def __dict__(self):
        return {
            'ssid': self.ssid,
            'password': self.password,
            'isLastUsed': self.isLastUsed
        }

    @staticmethod
    def fromDict(data):
        return SavedWifiNetwork(
            ssid=data['ssid'],
            password=data.get('password', None),
            isLastUsed=bool(data.get('isLastUsed', False))
        )
