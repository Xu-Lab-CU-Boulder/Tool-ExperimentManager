"""Camera temperatures: reading a GenICam remote module, without hardware."""

import json

from experimentkit import cameras


class FakeRemote:
    """Just enough of eGrabber's RemoteModule: get, set, features."""

    def __init__(self, values, selector_temps=None):
        self.values = dict(values)
        self.selector_temps = selector_temps or {}
        self.writes = []

    def features(self):
        names = list(self.values)
        if self.selector_temps:
            names += [cameras.SELECTOR, cameras.TEMPERATURE]
        return names

    def get(self, feature, dtype=None):
        if feature == cameras.TEMPERATURE and self.selector_temps:
            return self.selector_temps[self.values[cameras.SELECTOR]]
        if feature not in self.values:
            raise KeyError(feature)
        return self.values[feature]

    def entries(self, feature):
        return list(self.selector_temps)

    def set(self, feature, value):
        self.writes.append((feature, value))
        self.values[feature] = value


IDENT = {"DeviceVendorName": "LaVision", "DeviceModelName": "CX-16", "DeviceSerialNumber": "123"}


def test_steps_through_the_selector_and_puts_it_back():
    remote = FakeRemote({**IDENT, cameras.SELECTOR: "Mainboard"},
                        {"Sensor": 31.5, "Mainboard": 40.25})

    r = cameras.read_remote(remote, 2)

    assert r.temperatures_c == {"Sensor": 31.5, "Mainboard": 40.25}
    assert remote.values[cameras.SELECTOR] == "Mainboard"  # restored
    assert all(f == cameras.SELECTOR for f, _ in remote.writes)  # nothing else written
    assert r.label == "LaVision CX-16 #123" and r.index == 2 and not r.problem


def test_plain_device_temperature_and_vendor_extras():
    remote = FakeRemote({**IDENT, cameras.TEMPERATURE: 36.0, "SensorTemperature": 30.0,
                         "TemperatureUnit": "C"})
    r = cameras.read_remote(remote)
    assert r.temperatures_c == {"Device": 36.0, "SensorTemperature": 30.0}
    assert remote.writes == []


def test_a_camera_without_temperatures_says_so():
    r = cameras.read_remote(FakeRemote(IDENT))
    assert r.temperatures_c == {} and r.problem == "no temperature feature found"


def test_log_rows_append_as_jsonl(tmp_path):
    r = cameras.CameraReading(0, "LaVision", "CX-16", "123", temperatures_c={"Sensor": 31.5})
    log = tmp_path / "temps.jsonl"
    cameras.append_log(log, cameras.log_rows([r], note="morning QC"))
    cameras.append_log(log, cameras.log_rows([r]))
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 2 and rows[0]["note"] == "morning QC"
    assert rows[0]["temperatures_c"] == {"Sensor": 31.5} and "when" in rows[0]


def test_cli_refuses_while_davis_runs(monkeypatch, capsys):
    from experimentkit import __main__ as cli

    monkeypatch.setattr(cli, "_davis_running", lambda: True)
    assert cli.main(["cameras", "temps"]) == 2
    assert "DaVis is running" in capsys.readouterr().err
