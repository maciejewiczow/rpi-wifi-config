import uasyncio
from wifiConfig.connectToSavedNetworks import connectToSavedNetworks

async def main():
    print(await connectToSavedNetworks())

uasyncio.run(main())
