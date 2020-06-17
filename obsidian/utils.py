from obsidian.log import Logger


# Packet Utils
def unpackageString(data, encoding="ascii"):
    Logger.verbose(f"Unpacking String {data}")
    # Decode Data From Bytes To String
    # Remove Excess Zeros
    return data.decode(encoding).strip()


def packageString(data, maxSize=64, encoding="ascii"):
    Logger.verbose(f"Packing String {data}")
    # Trim Text Down To maxSize
    # Fill Blank Space With Spaces Using ljust
    # Encode String Into Bytes Using Encoding
    return bytes(data[:maxSize].ljust(maxSize), encoding)
