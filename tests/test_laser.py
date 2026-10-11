"""The laser reader only ever asks questions."""

import pytest

from experimentkit import laser


class FakePort:
    def __init__(self, replies):
        self.replies = replies
        self.sent = []
        self.closed = False

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.sent.append(data.decode("ascii"))

    def readline(self):
        asked = self.sent[-1].strip()
        return (self.replies.get(asked, "") + "\r\n").encode("ascii")

    def close(self):
        self.closed = True


def test_every_command_it_can_send_is_a_question():
    assert laser.QUERIES and all(c.startswith("$") and c.endswith(" ?")
                                 for c in laser.QUERIES.values())


@pytest.mark.parametrize("command", ["$RUN", "$SHUTTER 1", "$STOP", "$L1VSET 50", "$LTEMP",
                                     "$QSW 1", "$LTEMP ?\r\n$RUN"])
def test_anything_but_a_listed_query_is_refused(command):
    port = FakePort({})
    with pytest.raises(laser.NotAQuery):
        laser._ask(port, command)
    assert port.sent == []  # nothing reached the port


def test_reads_every_query_once_and_closes_the_port():
    port = FakePort({"$LTEMP ?": "$LTEMP 33.5", "$TEMPF ?": "$TEMPF 70.0", "$STATE ?": "$STATE 78",
                     "$STATUS ?": "$STATU f800000000", "$SSHOT ?": "$SSHOT 36668151"})
    out = laser.read_laser(open_port=lambda: port)
    assert [s.strip() for s in port.sent] == list(laser.QUERIES.values())
    assert out["values"]["LTEMP"] == 33.5 and out["values"]["TEMPF"] == 70.0
    assert out["values"]["SSHOT"] == 36668151 and "STATUS" not in out["values"]
    assert out["raw"]["STATUS"] == "$STATU f800000000" and "STATE" not in out["values"] and port.closed
