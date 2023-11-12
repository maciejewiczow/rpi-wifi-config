import uasyncio
from wifiConfig import tryConnectingToKnownNetworks

async def main():
    print(await tryConnectingToKnownNetworks())

uasyncio.run(main())
