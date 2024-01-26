// hello world asm:

// self equality if by itself prohibited
// varN = varN / else = else / addr = addr // use else/addr/varN = 1 instead (ip/cond/acc/neg are exceptions)
// ip = ip / else = cond - nops
// acc has no = sign, but acc += a
// neg has no = sign, but neg = -a

// special cases:
// - addr = cond - it's using bit from the previous addr and if need to change, changes addr on the next instruction
// - cond = cond - will cause undefined behavior

// there are still two issues:
// - what to do with `cond = cond`
// - there is no way to move register contents to memory. Is it even needed? (whereas there is a way to move data from memory to a register)

// disscusion field:
// - neg now is used so it produces a number that is 0 when summed up with the src number, but it can be replaced with the literally bitwize flip
//  (seems that with bitwize flip a code will be bigger, but surely the machine will have less transistors, still the minimum propogation delay will surely not be affected. so the question is will really code increase?)

var1 = 1 // hardcoded requirement of `:=` and `=-=`, also used throughout this program (must not be modified from this moment e.g. var1 = 1 everywhere)

// jmp to init
ip =-= .init

@.loop // while mem[&msgend]
{
    // condition
    {
        // check pointer reached the end, jmp to halt if so
        addr = var0 // = &msgend
        ip = cond
    }

    // body
    {
        // stdout
        {
            // [assert var4 == ~else]
            // var5 = ~else
            var5 = var4

            // mem[var2] = mem[acc] - set data
            addr = acc // prepare to read msg bit
            var5 = cond // remember msg bit
            addr = var2 // = 2 // prepare to write bit at 2
            cond = var5 // write msg bit

            // mem[var3] = 1 - ttl clock
            addr = var3 // = 3 // prepare to write bit at 3
            cond = var1 // write 1 [assert else != 1] [assert var1 == 1]
        }

        // mark bit
        {
            addr = acc
            cond = else // write 0
        }

        // advance data pointer
        acc += var1
    }

    // jmp to top
    ip = var6  // = .loop
}

@.halt
{
    addr = var1
    cond = else // write 0
}

@.init
{
    // constants (must not be modified throughout of the program lifetime)
    var0 := &msgend
    var6 := .loop
    else := .halt

    neg = -acc
    acc += neg // acc = 0

    acc += var1
    acc += var1
    var2 = acc // var2 := 2
    acc += var1
    var3 = acc // var3 := 3

    // [assert else != ~else]
    neg = -else
    var4 = neg

    // volatile [assert acc = 3]
    acc += var1 // acc = 4 // from now on acc is only used as data pointer
    // var5 is for any other use

    // mem[&msgend] = 1
    addr = var0
    cond = var1

    // return to loop
    ip = var6 // = .loop
}