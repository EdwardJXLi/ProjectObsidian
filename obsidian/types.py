from typing import NewType, TypeVar
import re

# Regex for a valid IP
validIp = re.compile("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

# Temporary Types
T = TypeVar("T")

# Custom Type for Usernames
UsernameType = NewType("UsernameType", str)
def _formatUsername(name: str) -> UsernameType:
    return UsernameType(name.lower())

# Custom Type for Ips
IpType = NewType("IpType", str)
def _formatIp(ip: str) -> IpType:
    if not validIp.match(ip):
        raise TypeError("Invalid Ip Format")
    return IpType(ip)

# Format Names Into A Safer Format
def format_name(name):
    return re.sub(r'\W+', '', name.replace(" ", "_").lower())
