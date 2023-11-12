# rpi-wifi-config
MicroPyhon package that makes the device wifi connection configurable without serial interface access and without hard-coding the credentials.
It also saves the networks that is used to a specified file, and then later on restart tries to connect to the last used network,
or any other known network in range. If that does not succeed, it starts an access point with a captive portal website, that allows the user
to select a network and input it's password.

## Installation
```py
import mip
mip.install('github:maciejewiczow/rpi-wifi-config')
```

## Examples

### With default args
Try to connect to one of networks saved in the default file location, using the library internal captive portal webpage template, and
print the acquired ip address.
```py
import uasyncio
from wifiConfig import tryConnectingToKnownNetworks

async def main():
    print(await tryConnectingToKnownNetworks())

uasyncio.run(main())
```

### Custom config
Try to connect to one of networks saved in a `/example/file.json` file, if not possible start open access point named `Configure me`
with captive portal that uses the template `page.html` as the main page, passing values `val1` and `val2` to the template.
Finally print the acquired ip address.
```py
import uasyncio
from wifiConfig import tryConnectingToKnownNetworks

async def main():
    print(
        await tryConnectingToKnownNetworks(
            knownNetworksFilePath='/example/file.json',
            indexTemplatePath='page.html',
            apName='Configure me',
            val1=1,
            val2=2
        )
    )

uasyncio.run(main())
```

### Start config access point manually
```py
import uasyncio
from wifiConfig import startConfigurationAP

async def main():
    await startConfigurationAP()

uasyncio.run(main())
```
