// form 1:
// input: var0, var1, var2, var3
{
    // addr = 0
    {
        neg = -acc
        acc += neg
        addr = acc
    }

    else = var0
    cond = var1
    else = var2
    var3 = cond
}
// output:
//   var3 = if var0 == var1 then var2 else var3
// side effect:
//   mem[0] = var0 != var1
//   neg = -(old acc)
//   acc = 0
//   addr = 0
//   else = var2

// form 2:
// input: else, var0, var1, var2
// side input: addr
{
    cond = var0
    else = var1
    var2 = cond
}
// output:
//   var2 = if var0 == else then var1 else var2
// side effect:
//   mem[addr] = var0 != var1
//   else = var1