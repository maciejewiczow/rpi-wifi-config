import uasyncio
import json
from wifiConfig.KnownWifiNetwork import KnownWifiNetwork
from wifiConfig.ReachableWifiNetwork import ReachableWifiNetwork
from wifiConfig.util import dirname, assignDefault, find
from lib.phew.phew import connect_to_wifi, server, access_point, dns
from lib.phew.phew.template import render_template
from lib.phew.phew.server import redirect, Request
from lib.phew.phew.exceptions import APNotFoundException, ConnectingFailedException, WifiException, WrongPasswordException

class FileFormatError(Exception):
    pass

def test():
    print('test')

async def connectToSavedNetworks(
    knownNetworksFilePath = 'networks.json',
    indexTemplatePath = '/'.join([dirname(__file__), 'index.html']),
    apName = 'Raspberry Pico W',
    apPassword = None,
    wifiConnectionTimeoutSeconds = 30,
    domain = 'config.pico',
    **templateArgs
):
    """ Tries to connect to any of networks saved in the specified file. If that does not work, then starts a configuration access point """
    import network

    try:
        with open(knownNetworksFilePath, 'r') as f:
            networksData = json.load(f)
        print('Loaded saved networks')
    except OSError:
        print('Network file not found, creating empty one')
        networksData = []
        with open(knownNetworksFilePath, 'w') as f:
            f.write("[]\n")

    if type(networksData) is not list:
        raise FileFormatError("Thie wifi data file should contain a top-level array")

    if len(networksData) == 0:
        print('No saved networks, starting the access point')
        return await startConfigurationAP(
            apName=apName,
            indexTemplatePath=indexTemplatePath,
            knownNetworksFilePath=knownNetworksFilePath,
            knownNetworks=[],
            apPassword=apPassword,
            domain=domain,
            templateArgs=templateArgs,
        )

    knownNetworks = [KnownWifiNetwork.fromDict(network) for network in networksData]

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    reachableNetworks = [ReachableWifiNetwork(entry) for entry in wlan.scan()]
    reachableNetworks.sort(reverse=True, key = lambda network: network.signalStrength)

    lastUsedNetwork = find(knownNetworks, matcher=lambda net: net.isLastUsed)

    if lastUsedNetwork is not None and find(reachableNetworks, matcher=lambda net: lastUsedNetwork.ssid == net.ssid) is not None:
        try:
            result = await connect_to_wifi(
                ssid=lastUsedNetwork.ssid,
                password=lastUsedNetwork.password,
                timeout_seconds=wifiConnectionTimeoutSeconds
            )

            if result is not None:
                return result
        except WifiException:
            pass

    for net in reachableNetworks:
        saved = find(knownNetworks, matcher=lambda saved: saved.ssid == net.ssid)

        if saved is not None:
            try:
                result = await connect_to_wifi(ssid=saved.ssid, password=saved.password, timeout_seconds=wifiConnectionTimeoutSeconds)

                if result is not None:
                    return result
            except WifiException:
                pass

    return await startConfigurationAP(
        apName,
        indexTemplatePath,
        knownNetworksFilePath,
        knownNetworks,
        apPassword,
        domain,
        templateArgs
    )

async def startConfigurationAP(
    apName: str,
    indexTemplatePath: str,
    knownNetworksFilePath: str,
    knownNetworks,
    apPassword,
    domain: str,
    templateArgs
) -> str:
    ipAddrFromNewNetwork = None
    ap = access_point(ssid=apName, password=apPassword)

    @server.route("/", methods=['GET'])
    def index(_):
        networks = [ReachableWifiNetwork(net) for net in ap.scan()]
        networks.sort(reverse=True, key = lambda network: network.signalStrength)

        assignDefault(templateArgs, 'title', 'Configure the WiFi connectivity')
        templateArgs['rootDir'] = dirname(__file__)

        return render_template(indexTemplatePath, **templateArgs, networks=networks)

    @server.route("/connect", methods=['POST'], isAsync=True)
    async def connectToWifi(req: Request):
        nonlocal ipAddrFromNewNetwork
        nonlocal ap

        ssid = req.data.get('ssid', None)
        password = req.data.get('password', None)

        if ssid is None or password is None:
            return "Bad request body", 400

        try:
            ip = await connect_to_wifi(ssid, password)
        except WrongPasswordException:
            ap = access_point(ssid=apName, password=apPassword)
            return "Wrong password", 401
        except APNotFoundException:
            return "Unknown SSID", 404
        except ConnectingFailedException:
            ap = access_point(ssid=apName, password=apPassword)
            return  "Failed to connect", 408

        if ip is None:
            ap = access_point(ssid=apName, password=apPassword)
            return "Failed to connect", 408

        ipAddrFromNewNetwork = ip

        knownNet = find(enumerate(knownNetworks), matcher=lambda net: net[1].ssid == ssid)

        newNet = KnownWifiNetwork(
            ssid=ssid,
            password=password,
            isLastUsed=True
        )

        for net in knownNetworks:
            net.isLastUsed = False

        if knownNet is None:
            knownNetworks.append(newNet)
        else:
            knownNetworks[knownNet[0]] = newNet

        with open(knownNetworksFilePath, 'w') as f:
            json.dump([net.__dict__ for net in knownNetworks], f)

        srvTask.cancel()
        return "Connected", 200

    @server.catchall()
    def catch_all(_):
        return redirect("http://" + domain + "/")

    ip = ap.ifconfig()[0]
    dnsTask = dns.run_catchall(ip)
    srvTask = server.run(host=ip)

    # awaiting the server task did not work
    while ipAddrFromNewNetwork is None:
        await uasyncio.sleep_ms(300)

    dnsTask.cancel()

    if ipAddrFromNewNetwork is None:
        raise RuntimeError("New ip was None after server was shut down. This should not have been possible")

    return ipAddrFromNewNetwork
