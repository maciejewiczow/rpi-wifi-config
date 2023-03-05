from typing import Any, Dict, List, Optional
import json
from SavedWifiNetwork import SavedWifiNetwork
from lib.phew.phew import connect_to_wifi, server, access_point, dns
from lib.phew.phew.template import render_template
from lib.phew.phew.server import redirect, Request
from lib.phew.phew.exceptions import APNotFoundException, ConnectingFailedException, WifiException, WrongPasswordException
from ReachableWifiNetwork import ReachableWifiNetwork
from src.util import dirname
from util import assignDefault, find
import uasyncio

class FileFormatError(Exception):
    pass

async def connectToSavedNetworkOrStartConfigurationAP(
    savedNetworksFilePath = 'networks.json',
    indexTemplatePath = '/'.join([dirname(__file__), 'index.html']),
    apName = 'Raspberry Pico W',
    apPassword: Optional[str] = None,
    wifiConnectionTimeoutSeconds = 30,
    domain = 'config.pico',
    **templateArgs
) -> Optional[str]:
    import network

    try:
        with open(savedNetworksFilePath, 'r') as f:
            networksData = json.load(f)
    except FileNotFoundError:
        networksData = []
        with open(savedNetworksFilePath, 'w') as f:
            f.write("[]\n")

    if type(networksData) is not list:
        raise FileFormatError("Thie wifi data file should contain a top-level array")

    if len(networksData) == 0:
        return await startConfigurationAP(
            apName=apName,
            indexTemplatePath=indexTemplatePath,
            savedNetworksFilePath=savedNetworksFilePath,
            savedNetworks=[],
            apPassword=apPassword,
            domain=domain,
            templateArgs=templateArgs,
        )

    savedNetworks = [SavedWifiNetwork.fromDict(network) for network in networksData]

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    reachableNetworks = [ReachableWifiNetwork(entry) for entry in wlan.scan()]
    reachableNetworks.sort(reverse=True, key = lambda network: network.signalStrength)

    lastUsedNetwork = find(savedNetworks, matcher=lambda net: net.isLastUsed)

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
        saved = find(savedNetworks, matcher=lambda saved: saved.ssid == net.ssid)

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
        savedNetworksFilePath,
        savedNetworks,
        apPassword,
        domain,
        templateArgs
    )

async def startConfigurationAP(
    apName: str,
    indexTemplatePath: str,
    savedNetworksFilePath: str,
    savedNetworks: List[SavedWifiNetwork],
    apPassword: Optional[str],
    domain: str,
    templateArgs: Dict[str, Any]
) -> str:
    ipAddrFromNewNetwork: Optional[str] = None
    ap = access_point(ssid=apName, password=apPassword)

    @server.route("/", methods=['GET'])
    def index(_):
        networks = [ReachableWifiNetwork(net) for net in ap.scan()]
        networks.sort(reverse=True, key = lambda network: network.signalStrength)

        assignDefault(templateArgs, 'title', 'Configure the WiFi connectivity')
        templateArgs['__dirname__'] = dirname(__file__)

        return render_template(indexTemplatePath, **templateArgs, networks=networks)

    @server.route("/connect", methods=['POST'])
    async def connectToWifi(req: Request):
        nonlocal ipAddrFromNewNetwork

        ssid = req.data.get('ssid', None)
        password = req.data.get('password', None)

        if ssid is None or password is None:
            return "Bad request body", 400

        try:
            ip = await connect_to_wifi(ssid, password)
        except WrongPasswordException:
            return "Wrong password", 401
        except APNotFoundException:
            return "Unknown SSID", 404
        except ConnectingFailedException:
            return "Failed to connect", 408

        if ip is None:
            return "Failed to connect", 408

        ipAddrFromNewNetwork = ip

        savedNet = find(enumerate(savedNetworks), matcher=lambda net: net[1].ssid == ssid)

        newNet = SavedWifiNetwork(
            ssid=ssid,
            password=password,
            isLastUsed=True
        )

        for net in savedNetworks:
            net.isLastUsed = False

        if savedNet is None:
            savedNetworks.append(newNet)
        else:
            savedNetworks[savedNet[0]] = newNet

        with open(savedNetworksFilePath, 'w') as f:
            json.dump([net.__dict__ for net in savedNetworks], f)

        srvTask.cancel()
        return "Connected", 200

    @server.catchall()
    def catch_all(_):
        return redirect("http://" + domain + "/")

    ip = ap.ifconfig()[0]
    dnsTask = dns.run_catchall(ip)
    srvTask = server.run(host=ip)

    try:
        await srvTask
    except uasyncio.CancelledError:
        dnsTask.cancel()

    if ipAddrFromNewNetwork is None:
        raise RuntimeError("New ip was None after server was shut down. This should not have been possible")

    return ipAddrFromNewNetwork
