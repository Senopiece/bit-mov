from dataclasses import dataclass
from math import ceil
import re
import sys
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class Return:
    content: List[int]
    new_labels_offsets: List[int]

    def __init__(
        self,
        content: List[int] = [],
        new_labels_offsets: List[int] = [],
    ):
        self.content = content
        self.new_labels_offsets = new_labels_offsets


@dataclass
class Command:
    regex: re.Pattern[Any]
    func: Callable[..., Return]
    eval: Callable[[int, Tuple[str], List[int]], Tuple[List[int], List[int]]]
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

# basic registers
param_resolvers.append(
    ParamT(
        selector=re.compile(r"R"),
        resolve=lambda sm, arg, lbls: arg if arg in regs else None,
        label=lambda sm, arg: None,
    )
)

# variables
param_resolvers.append(
    ParamT(
        selector=re.compile(r"V"),
        resolve=lambda sm, arg, lbls: arg if arg.startswith("var") else None,
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

AUGMENTATTIONS: Dict[str, int] = {}

# use augmentations
param_resolvers.append(
    ParamT(
        selector=re.compile(r"E"),
        resolve=lambda sm, arg, lbls: AUGMENTATTIONS[arg[1:]]
        if arg.startswith("&")
        else None,
        label=lambda sm, arg: None,
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
            return res.content, res.new_labels_offsets

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


acc_reg = 0
ip_reg = 1
neg_reg = 2
addr_reg = 3
cond_reg = 4
else_reg = 5

regs = {
    "acc": acc_reg,
    "ip": ip_reg,
    "neg": neg_reg,
    "addr": addr_reg,
    "cond": cond_reg,
    "else": else_reg,
}


def resolve_reg(s: str | int):
    if isinstance(s, int):
        v = s
    elif s in regs:
        return regs[s]
    elif s.startswith("var"):
        si = int(s[3:])
        v = si + len(regs)
        if v > registers_count - 1:
            raise ValueError(f"No var{si}")
    else:
        raise ValueError(f"Invalid token <{s}>")

    return v


def resolve_regs(*args: str | int):
    return [resolve_reg(x) for x in args]


@add_to_commands("{")
def br_l(_: int, *args: str | int):
    return Return()


@add_to_commands("}")
def br_r(_: int, *args: str | int):
    return Return()


@add_to_commands("{:R|V:} = 1")
def store1(offset: int, *args: str | int):
    (n,) = resolve_regs(*args)
    assert n not in (ip_reg, cond_reg, acc_reg, neg_reg)
    if debug:
        print(f"reg{n} = 1 at {hex(offset)}")
    return Return(content=[int(mb(n, r) + mb(n, r), base=2)])


@add_to_commands("acc += {:R|V:}")
def acc(offset: int, *args: str | int):
    (n,) = resolve_regs(*args)
    if debug:
        print(f"acc += reg{n} at {hex(offset)}")
    return Return(content=[int(mb(acc_reg, r) + mb(n, r), base=2)])


@add_to_commands("neg = -{:R|V:}")
def neg(offset: int, *args: str | int):
    (n,) = resolve_regs(*args)
    if debug:
        print(f"neg = -reg{n} at {hex(offset)}")
    return Return(content=[int(mb(neg_reg, r) + mb(n, r), base=2)])


@add_to_commands("{:R|V:} = {:R|V:}")
def mov(offset: int, *args: str | int):
    n, m = resolve_regs(*args)
    assert n not in (acc_reg, neg_reg)
    assert n != m or n in (ip_reg, cond_reg)
    if debug:
        print(f"reg{n} = reg{m} at {hex(offset)}")
    return Return(content=[int(mb(n, r) + mb(m, r), base=2)])


@add_to_commands("{:S:} := {:X|E|N:}")
def mov_const_effective(offset: int, _n: str, const: int):
    n = resolve_reg(_n)
    res: List[int] = []

    # NOTE: hardcoded for now
    reg_const_1 = resolve_reg("var1")

    if debug:
        print(f"// reg{n} := {const} start")

    if debug:
        print("// init acc = 0")

    def movf(a: int, b: int):
        nonlocal offset
        res = mov.func(offset, a, b).content
        offset += len(res)
        return res

    def negf(a: int):
        nonlocal offset
        res = neg.func(offset, a).content
        offset += len(res)
        return res

    def accf(a: int):
        nonlocal offset
        res = acc.func(offset, a).content
        offset += len(res)
        return res

    # init acc = 0
    res += negf(acc_reg)
    res += accf(neg_reg)

    has_1 = False

    # for each bit
    for bit in mb(const, sizeofreg):
        # *2
        if has_1:
            if debug:
                print("// *2")
            res += accf(acc_reg)

        # +1
        if bit == "1":
            if debug:
                print("// +1")
            has_1 = True
            res += accf(reg_const_1)

    # store the final result
    res += movf(n, acc_reg)

    if debug:
        print(f"// reg{n} = {const} end")

    return Return(res)


@add_to_commands("{:S:} =-= {:X|E|N:}")
def mov_const(offset: int, _n: str, const: int):
    n = resolve_reg(_n)
    res: List[int] = []

    # NOTE: hardcoded for now
    reg_const_1 = resolve_reg("var1")

    if debug:
        print(f"// reg{n} = {const} start")

    def movf(a: int, b: int):
        nonlocal offset
        res = mov.func(offset, a, b).content
        offset += len(res)
        return res

    def accf(a: int):
        nonlocal offset
        res = acc.func(offset, a).content
        offset += len(res)
        return res

    # for each bit
    for bit in mb(const, sizeofreg):
        if debug:
            print("// *2")

        # *2
        res += accf(acc_reg)

        if debug:
            print(f"// +{1 if bit == '1' else 0}")

        # maybe +1
        # TODO: can be reduced on zeros if allow macros with dynamic size
        if bit == "1":
            res += accf(reg_const_1)
        else:
            res += movf(ip_reg, ip_reg)

    # store the final result
    res += movf(n, acc_reg)

    if debug:
        print(f"// reg{n} = {const} end")

    return Return(res)


@add_to_commands("{:L:}")
def decl_label(offset: int):
    return Return([], [offset])


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
    sizeofmem = (
        2**sizeofreg
    )  # number of instructions avaliable to be stored in ROM / number of bits in RAM

    for e in rest:
        e = e.strip()
        if e.startswith("--aug-"):
            e = e[6:]
            aug, val = e.split("=")
            AUGMENTATTIONS[aug] = int(val)

    # fictive run
    offset = 0
    with open(filename, "r") as f:
        for line in f:
            line = line.split("//")[0].strip()
            if line == "":
                continue
            ret = asm_to_bin(offset, line, True)
            offset += len(ret)

    if len(rest) > 0:
        debug = "--debug" in rest

    if debug:
        print([(k, hex(v), v) for k, v in labels_decls.items()])

    # actual run
    content: List[int] = []
    with open(filename, "r") as f:
        for line in f:
            src = line.strip()
            line = line.split("//")[0].strip()
            if line == "":
                continue
            ret = asm_to_bin(len(content), line, False)
            content += ret

    match outformat:
        case "sim":
            with open(filename + ".sim", "wt") as f:
                f.write("v2.0 raw\n")
                f.write(" ".join(map(lambda x: hex(x)[2:], content)))

        case _:
            raise ValueError("unknown out format")

    rams = int(ceil(sizeofmem / 8))  # RAM size in bytes
    psbi = len(content)  # program size in instructions
    print(
        "Executable size:",
        psbi,
        "instructions",
        f"[ {int(100*psbi/sizeofmem)} % ]",
    )
    print("Avaliable RAM size:", sizeofmem, "bits", "=", format_bytes(rams))
