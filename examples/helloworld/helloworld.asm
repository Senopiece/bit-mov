// hello world asm:

// jmp to init
ip =-= .init

@.loop // while !mem[&msgend]
{
    // condition
    {
        // check pointer reached the end, jmp to halt if so
        addr = var0 // = &msgend
        ip = cond
    }

    @.body
    {
        // stdout
        {
            // mem[var2] = mem[var4] - set data
            addr = var4 // read msg bit
            var5 = cond // remember msg bit
            addr = var2 // = 2 // prepare to write bit at 2
            cond = var5 // write msg bit

            // mem[var3] = 1 - ttl clock
            addr = var3 // = 3 // prepare to write bit at 3
            cond = if // write 1
        }

        // mark bit
        {
            addr = var4
            cond = if // write 1
        }

        // advance data pointer
        a = var4
        var4 = sum
    }

    // jmp to top
    ip = var1  // = .loop
}

@.halt
{
    addr = const 1
    cond = else // write 0
}

@.init
{
    // as if/else are not modified anywhere else, they can be used as-is
    if := .halt
    else := .body
    b = const 1

    // constants
    var0 := &msgend
    var1 := .loop
    a = const 1
    var2 = sum // var2 := 2
    a = var2
    var3 = sum // var3 := 3

    // volatile
    a = var3
    var4 = sum // var4 := 4 // data pointer
    // var5 is for any other use
    // a is for arbitary incrementation

    // return to loop
    ip = var1 // = .loop
}