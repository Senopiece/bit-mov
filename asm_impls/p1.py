from dataclasses import dataclass
from math import ceil
import re
import sys
from typing import Any, Callable, List, Tuple


@dataclass
class Return:
    content: str
    new_labels_offsets: List[int]

    @property
    def hex(self) -> str:
        raise NotImplementedError()

    @property
    def bin(self) -> str:
        raise NotImplementedError()

    @property
    def get(self) -> str:
        raise NotImplementedError()


@dataclass
class HexReturn(Return):
    def __init__(self, content: str, new_labels_offsets: List[int] | None = None):
        # assert content is of hex symbols
        self.content = content
        self.new_labels_offsets = (
            new_labels_offsets if new_labels_offsets is not None else []
        )

    @property
    def bin(self):
        return bin(int(self.content, 16))[2:]

    @property
    def hex(self):
        return self.content

    @property
    def get(self):
        return "0x" + self.content


@dataclass
class BinReturn(Return):
    def __init__(self, content: str, new_labels_offsets: List[int] | None = None):
        # assert content is of binary symbols
        self.content = content
        self.new_labels_offsets = (
            new_labels_offsets if new_labels_offsets is not None else []
        )

    @property
    def bin(self):
        return self.content

    @property
    def hex(self):
        return hex(int(self.content, 2))[2:]

    @property
    def get(self):
        return "0xb" + self.content


@dataclass
class Command:
    regex: re.Pattern[Any]
    func: Callable[..., Return]
    eval: Callable[[int, Tuple[str], List[int]], Tuple[str, List[int]]]
    info: Callable[[Tuple[str]], Tuple[List[str], List[str]]]


commands: List[Command] = []
r: int  # registers_count = 2**r

registers_count: int
sizeofreg: int
sizeofmem: int

parambr = re.compile(r"\{:(\S+?):\}")


class NotPass:
    pass


@dataclass
class Label:
    name: str
    is_new: bool

    @staticmethod
    def new(name: str):
        return Label(name=name, is_new=True)

    @staticmethod
    def use(name: str):
        return Label(name=name, is_new=False)


@dataclass
class ParamResolver:
    resolve: Callable[
        [str, List[int]], NotPass | None | Any
    ]  # (matched arg, labels) => NotPass - do not pass to the func | None - unresolved | res - resolved value to pass
    label: Callable[[str], Label | None]  # (matched arg) => label | None


@dataclass
class ParamT:
    selector: re.Pattern[Any]
    resolve: Callable[
        [str, str, List[int]], Any
    ]  # (matched_selector, matched arg, labels) => res | None
    label: Callable[[str, str], Label | None]  # (matched_selector, matched arg)

    def gen_resolver(self, s: str):
        matched_selector = self.selector.fullmatch(s)
        if matched_selector is None:
            return None
        return ParamResolver(
            resolve=lambda arg, lbs: self.resolve(s, arg, lbs),
            label=lambda arg: self.label(s, arg),
        )


param_resolvers: List[ParamT] = []

# any number
param_resolvers.append(
    ParamT(
        selector=re.compile(r"N"),
        resolve=lambda sm, arg, lbls: int(arg, base=0),
        label=lambda sm, arg: None,
    )
)

# any string
param_resolvers.append(
    ParamT(
        selector=re.compile(r"S"),
        resolve=lambda sm, arg, lbls: arg,
        label=lambda sm, arg: None,
    )
)

lr = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*")


def _extract_use_label(s: str):
    if not ((lr.fullmatch(s[1:]) is not None) and s.startswith(".")):
        raise ValueError("Invalid label usage : " + s)
    return s[1:]


# use label
param_resolvers.append(
    ParamT(
        selector=re.compile(r"X"),
        resolve=lambda sm, arg, lbls: lbls.pop(0) if arg.startswith(".") else None,
        label=lambda sm, arg: Label.use(_extract_use_label(arg))
        if arg.startswith(".")
        else None,
    )
)


def _extract_define_label(s: str):
    if not ((lr.fullmatch(s[2:]) is not None) and s.startswith("@.")):
        raise ValueError("Invalid label declaration : " + s)
    return s[2:]


# declare label
param_resolvers.append(
    ParamT(
        selector=re.compile(r"L"),
        resolve=lambda sm, arg, lbls: NotPass() if arg.startswith("@.") else None,
        label=lambda sm, arg: Label.new(_extract_define_label(arg))
        if arg.startswith("@.")
        else None,
    )
)

# any exact string
param_resolvers.append(
    ParamT(
        selector=re.compile(r"\`\S*\`"),
        resolve=lambda sm, arg, lbls: arg if arg == sm[1:-1] else None,
        label=lambda sm, arg: None,
    )
)


def get_param_resolver(s: str):
    for rlvr in param_resolvers:
        r = rlvr.gen_resolver(s)
        if r is not None:
            return r
    raise AssertionError(f"Failed to find parameter resolver for {s}")


def get_mixed_params_resolver(s: str):
    mix = s.split("|")
    assert len(mix) != 0, f"Empty mixed param: {mix}"
    return [get_param_resolver(e) for e in mix]


def add_to_commands(pattern: str) -> Callable[..., Command]:
    def decorate(func: Callable[..., Return]) -> Command:
        escaped_pattern = re.escape(pattern).replace(r"\{:", "{:").replace(r":\}", ":}")
        regex_pattern = parambr.sub(r"(.*)", escaped_pattern)
        regex = re.compile(rf"^{regex_pattern}$")
        params = [get_mixed_params_resolver(p) for p in parambr.findall(pattern)]

        def eval(offset: int, args: Tuple[str], labels: List[int]):
            cargs: List[Any] = []
            for param, arg in zip(params, args):
                for resolvep in param:
                    carg = resolvep.resolve(arg, labels)
                    if isinstance(carg, NotPass):
                        break
                    if carg is not None:
                        cargs.append(carg)
                        break
                else:
                    raise ValueError(f"invalid value : {arg}")
            res = func(offset, *cargs)
            return res.bin, res.new_labels_offsets

        def labels_wrapper(args: Tuple[str]):
            new_labels: List[str] = []
            use_labels: List[str] = []
            for param, arg in zip(params, args):
                for resolvep in param:
                    lbl = resolvep.label(arg)
                    if isinstance(lbl, Label):
                        (new_labels if lbl.is_new else use_labels).append(lbl.name)
                        break  # one label per parameter
            return new_labels, use_labels

        cmd = Command(
            regex=regex,
            func=func,
            eval=eval,
            info=labels_wrapper,
        )
        commands.append(cmd)
        return cmd

    return decorate


def mb(n: int, size: int):
    n %= 2**size
    return f"{n:0{size}b}"


reg_const_0 = 0
reg_const_1 = 1
src_reg = 2
dst_reg = 3
ip_reg = 4
else_reg = 5
if_reg = 6
cond_reg = 7
a_reg = 8
b_reg = 9
sum_reg = 10

regs = {
    "Const0": reg_const_0,
    "Const1": reg_const_1,
    "Src": src_reg,
    "Dst": dst_reg,
    "IP": ip_reg,
    "Else": else_reg,
    "If": if_reg,
    "Cond": cond_reg,
    "A": a_reg,
    "B": b_reg,
    "Sum": sum_reg,
}


def resolve_reg(s: str | int):
    if isinstance(s, int):
        v = s
    else:
        if s in regs:
            return regs[s]
        si = int(s)
        v = si + len(regs)
        if v > 15:
            raise ValueError(f"No reg{si}")
    return v


def resolve_regs(*args: str | int):
    return [resolve_reg(x) for x in args]


@add_to_commands("reg{:S:} = reg{:S:}")
def mov(offset: int, *args: str | int):
    n, m = resolve_regs(*args)
    if debug:
        print(f"reg{n} = reg{m} at {hex(offset)}")
    res = ""
    for a, b in zip(mb(m, r), mb(n, r)):
        res += a + b
    return BinReturn(res)


@add_to_commands("reg{:S:} = {:X|N:}")
def mov_const(offset: int, _n: str, const: int):
    n = resolve_reg(_n)
    res = ""

    if debug:
        print(f"// reg{n} = {const} start")

    if debug:
        print("// init 0")

    def movf(a: int, b: int):
        nonlocal offset
        res = mov.func(offset, a, b).bin
        offset += len(res)
        return res

    # init 0
    res += movf(a_reg, reg_const_0)
    res += movf(b_reg, reg_const_0)

    # for each bit
    for bit in mb(const, sizeofreg):
        if debug:
            print("// *2")

        # *2
        res += movf(b_reg, a_reg)
        res += movf(a_reg, sum_reg)

        if debug:
            print(f"// +{1 if bit == '1' else 0}")

        # +1
        # TODO: can be reduced on zeros if allow macros with dynamic size
        res += movf(b_reg, reg_const_1 if bit == "1" else reg_const_0)
        res += movf(a_reg, sum_reg)

    # store the final result
    res += movf(n, a_reg)

    if debug:
        print(f"// reg{n} = {const} end")

    return BinReturn(res)


@add_to_commands('#store_ascii "{:S:}"')
def store_ascii(_, s: str):
    s = s.encode().decode("unicode-escape")
    res = ""
    for ch in s:
        d = f"{ord(ch):07b}"
        if debug:
            print(d)
        res += d
    return BinReturn(res)


@add_to_commands("#store 0xb{:S:}")
def store_bin(_, s: str):
    assert all(ch in ["0", "1"] for ch in s)
    return BinReturn(s)


@add_to_commands("{:L:}")
def decl_label(offset: int):
    return BinReturn("", [offset])


labels_decls = {}


def asm_to_bin(offset: int, msg: str, fictive: bool):
    for cmd in commands:
        match = cmd.regex.search(msg)
        if match is None:
            continue
        args: Tuple[str] = match.groups()  # type: ignore
        new_labels, use_labels = cmd.info(args)
        bdata, new_labels_offsets = cmd.eval(
            offset, args, [(0 if fictive else labels_decls[k]) for k in use_labels]
        )
        if fictive:
            for k, v in zip(new_labels, new_labels_offsets):
                labels_decls[k] = v
        return bdata
    else:
        raise ValueError(msg)


def format_bytes(n: int):
    return f"{n} byte{'s' if n > 10 and n % 10 != 1 else ''}"


debug = False

if __name__ == "__main__":
    _, _r, _m, filename, outformat, *rest = sys.argv
    r = int(_r)

    registers_count = 2**r
    sizeofreg = int(_m)
    sizeofmem = 2**sizeofreg

    # fictive run
    offset = 4
    with open(filename, "r") as f:
        for line in f:
            line = line.split("//")[0].strip()
            if line == "":
                continue
            ret = asm_to_bin(offset, line, True)
            offset += len(ret)

    if len(rest) > 0:
        debug = rest[0] == "--debug"

    if debug:
        print([(k, hex(v), v) for k, v in labels_decls.items()])

    # actual run
    content = "0100"
    with open(filename, "r") as f:
        for line in f:
            src = line.strip()
            line = line.split("//")[0].strip()
            if line == "":
                continue
            ret = asm_to_bin(len(content), line, False)
            content += ret

    match outformat:
        case "bin":
            # Adjust the last byte and write to the binary file
            while len(content) % 8 != 0:
                content += "0"  # Fill the remaining bits with zeros

            # Convert binary content to bytes
            binary_bytes = bytes(
                int(content[i : i + 8], 2) for i in range(0, len(content), 8)
            )

            # Write to the binary file
            with open(filename + ".bin", "wb") as binary_file:
                binary_file.write(binary_bytes)

        case "sim":
            with open(filename + ".sim", "wt") as f:
                f.write("v2.0 raw\n")
                f.write(" ".join(content))

        case _:
            raise ValueError("unknown out format")

    smb = sizeofmem // 8
    lb = int(ceil(len(content) / 8))
    print("Memory size:", smb, "bytes")
    print("Executable size:", format_bytes(lb), f"[ {int(100*lb/smb)} % ]")
    print("Free space remaining:", format_bytes(smb - lb))
