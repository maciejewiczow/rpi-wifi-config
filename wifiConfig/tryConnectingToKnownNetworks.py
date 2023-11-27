import uasyncio
import json
from .KnownWifiNetwork import KnownWifiNetwork
from .ReachableWifiNetwork import ReachableWifiNetwork
from .util import dirname, assignDefault, find
from lib.phew import connect_to_wifi, server, access_point, dns, render_template
from lib.phew.server import Request, redirect
from lib.phew.exceptions import SSIDNotFoundException, ConnectingFailedException, WifiException, WrongPasswordException

class FileFormatError(Exception):
    pass

def readKnownNetworks(knownNetworksFilePath: str):
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

    return [KnownWifiNetwork.fromDict(network) for network in networksData]

async def tryConnectingToKnownNetworks(
    knownNetworksFilePath = 'networks.json',
    indexTemplatePath = '/'.join([dirname(__file__), 'index.html']),
    apName = 'Raspberry Pico W',
    apPassword = None,
    wifiConnectionTimeoutSeconds = 10,
    domain = 'config.pico',
    **templateArgs
):
    """Try connectting to a known wifi network or start a configuration access point if that fails

    Tries to connect to any of networks saved in the specified file that are in range (first tries the one that was used the last time).
    If that does not work, then starts a configuration access point with a captive portal,
    serving a web page that allows the user to configure the desired Wifi credentials. The credentials are then saved in the file for future use.

    Arguments:
        knownNetworkFilePath - path to the file that contains a list of known networks in a json format. If the specified file does not exist,
            it will be created
        indexTemplatePath - path to the template (see [templates](https://github.com/maciejewiczow/phew#templates)) that will be rendered as the index
            page of the captive portal. The template will get a list of reachable wifi networks in a 'networks' parameter
        apName - the desired SSID of the access point that will be started
        apPassword - password of the access point. Pass None for open access point
        wifiConnectionTimeout - how long should the function wait before giving up on trying to connect to networks
        domain - the captive portal domain
        templateArgs - additional arguments that will be passed to the index template of the captive portal

    Return:
        Returns a tuple with:
            the ip address acquired after connecting to one of the available networks
            the network ssid
            the network password
    """
    import network

    knownNetworks = readKnownNetworks(knownNetworksFilePath)

    if len(knownNetworks) == 0:
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
                return result, lastUsedNetwork.ssid, lastUsedNetwork.password
        except WifiException:
            pass

    for net in reachableNetworks:
        saved = find(knownNetworks, matcher=lambda saved: saved.ssid == net.ssid)

        if saved is not None:
            try:
                result = await connect_to_wifi(ssid=saved.ssid, password=saved.password, timeout_seconds=wifiConnectionTimeoutSeconds)

                if result is not None:
                    return result, saved.ssid, saved.password
            except WifiException:
                pass

    return await startConfigurationAP(
        apName,
        indexTemplatePath,
        knownNetworksFilePath,
        apPassword,
        domain,
        templateArgs,
        knownNetworks,
    )

async def startConfigurationAP(
    apName = 'Raspberry Pico W',
    indexTemplatePath = '/'.join([dirname(__file__), 'index.html']),
    knownNetworksFilePath = 'networks.json',
    apPassword = None,
    domain = 'config.pico',
    templateArgs = {},
    knownNetworks = None,
):
    ipAddrFromNewNetwork = None
    ssid = None
    password = None
    ap = access_point(ssid=apName, password=apPassword)

    if knownNetworks is None:
        knownNetworks = readKnownNetworks(knownNetworksFilePath)

    @server.route("/", methods=['GET'])
    def index(_):
        networks = [ReachableWifiNetwork(net) for net in ap.scan()]
        networks.sort(reverse=True, key = lambda network: network.signalStrength)

        assignDefault(templateArgs, 'title', 'Configure the WiFi connectivity')
        assignDefault(templateArgs, 'rootDir', dirname(__file__))

        return render_template(indexTemplatePath, **templateArgs, networks=networks)

    @server.route("/connect", methods=['POST'], isAsync=True)
    async def connectToWifi(req: Request):
        nonlocal ipAddrFromNewNetwork
        nonlocal ssid
        nonlocal password
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
        except SSIDNotFoundException:
            return "Unknown SSID", 404
        except ConnectingFailedException:
            ap = access_point(ssid=apName, password=apPassword)
            return  "Failed to connect", 408

        if ip is None:
            ap = access_point(ssid=apName, password=apPassword)
            return "Failed to connect", 408

        ipAddrFromNewNetwork = ip

        knownNet = find(knownNetworks, matcher=lambda net: net.ssid == ssid)

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

    return ipAddrFromNewNetwork, ssid, password
