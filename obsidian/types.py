from typing import NewType, TypeVar
import re

# Regex for a valid IP
validIp = re.compile(r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

# Temporary Types
T = TypeVar("T")

# Custom Types
UsernameType = NewType("UsernameType", str)
IpType = NewType("IpType", str)


# Formatting Functions
def _formatUsername(name: str) -> UsernameType:
    return UsernameType(name.lower())


def _formatIp(ip: str) -> IpType:
    if not validIp.match(ip):
        raise TypeError("Invalid Ip Format")
    return IpType(ip)


def formatName(name):
    return re.sub(r'\W+', '', name.replace(" ", "_").lower())
