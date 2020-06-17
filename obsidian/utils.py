from os import listdir
from os.path import isfile

from obsidian.log import Logger


# Module Utils
def getFiles(filepath, extention=None, removeExtention=False):
    Logger.debug(f"Scanning Dir {filepath}")
    files = []
    # Ensure extention variable has '.' char
    if extention is not None:
        if extention[:1] != '.':
            Logger.verbose(f"Adding '.' to file extention {extention}")
            extention = '.' + extention
    # Loop Through Entire Folder
    for f in listdir(filepath):
        if isfile(filepath + f):
            Logger.verbose(f"Detected File {f}")
            # If extention is defined, check file type. Else; just append file name
            if extention is not None:
                # Check if last characters meet extention
                if f[-len(extention):] == extention:
                    Logger.verbose(f"File {f} Meets Extention Requirement")
                    # If removeExtention, append removed string. Else just append file
                    if removeExtention:
                        files.append(f[:-len(extention)])  # Return file name with last X characters removed
                    else:
                        files.append(f)
            else:
                files.append(f)
    return files


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
