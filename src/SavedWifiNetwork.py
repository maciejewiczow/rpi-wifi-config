from typing import Any, Dict, Optional

class SavedWifiNetwork:
    ssid: str
    password: Optional[str]
    isLastUsed: bool

    def __init__(self, ssid: str, password: Optional[str], isLastUsed = False):
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
    def fromDict(data: Dict[str, Any]):
        return SavedWifiNetwork(
            ssid=data['ssid'],
            password=data.get('password', None),
            isLastUsed=bool(data.get('isLastUsed', False))
        )
