# creates a sim file for initial ram with provided message


import sys


def msggen(s: str):
    s = s.encode().decode("unicode-escape")
    res = ""
    for ch in s:
        d = f"{ord(ch):07b}"
        res += d
    return res


if __name__ == "__main__":
    _, filename, s = sys.argv

    content = "0100" + msggen(s)

    print(len(content))  # print bits of data to store

    with open(filename + ".sim", "wt") as f:
        f.write("v2.0 raw\n")
        f.write(" ".join(content))
