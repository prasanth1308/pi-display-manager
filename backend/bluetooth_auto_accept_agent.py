#!/usr/bin/env python3
"""BlueZ auto-accept pairing agent (NoInputNoOutput).

This agent accepts pairing/auth requests without PIN entry.
"""

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib


BUS_NAME = "org.bluez"
AGENT_PATH = "/pi/display/agent"
AGENT_IFACE = "org.bluez.Agent1"
AGENT_MGR_IFACE = "org.bluez.AgentManager1"


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


class Agent(dbus.service.Object):
    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, _device):
        # Legacy PIN flows are not used in NoInputNoOutput mode.
        return "0000"

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, _device):
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def DisplayPasskey(self, _device, _passkey):
        pass

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, _device, _pincode):
        pass

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, _device, _passkey):
        # Auto-accept numeric comparison.
        return

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, _device):
        return

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, _device, _uuid):
        return

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        pass


def _trust_existing_devices(bus):
    om = dbus.Interface(bus.get_object(BUS_NAME, "/"), "org.freedesktop.DBus.ObjectManager")
    objects = om.GetManagedObjects()
    for path, ifaces in objects.items():
        props = ifaces.get("org.bluez.Device1")
        if not props:
            continue
        try:
            dev = dbus.Interface(bus.get_object(BUS_NAME, path), "org.freedesktop.DBus.Properties")
            dev.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
        except Exception:
            continue


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    Agent(bus, AGENT_PATH)
    manager = dbus.Interface(bus.get_object(BUS_NAME, "/org/bluez"), AGENT_MGR_IFACE)

    # NoInputNoOutput means no PIN/passkey UX on the Pi side.
    manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    manager.RequestDefaultAgent(AGENT_PATH)

    _trust_existing_devices(bus)

    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
