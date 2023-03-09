import uasyncio
from wifiConfig.tryConnectingToKnownNetworks import tryConnectingToKnownNetworks

async def main():
    print(await tryConnectingToKnownNetworks())

uasyncio.run(main())
