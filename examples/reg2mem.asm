// reg2mem is based on the following concept:
// 0<..x..> + (0<..x..> + 1<..0..>) = 1<..x..>
// 1<..x..> + (1<..x..> + 1<..0..>) = 1<..x..>
// NOTE: that can NOT be simplified to:
// 2*0<..x..> + 1<..0..> = 1<..x..>
// 2*1<..x..> + 1<..0..> = 1<..x..>
// since
// 2*0<..x..> + 1<..0..> = <..x..>0 + 1<..0..> that is not always 1<..x..>
// 2*1<..x..> + 1<..0..> = <..x..>0 + 1<..0..> that is not always 1<..x..>
// (yea, order of operations is crucial)

// so the core code based on this concept is:
// input: x
// side input: 1<..0..>
// {
//    neg = -acc
//    acc += neg // acc = 0
//    acc += x // acc = x
//    acc += 1<..0..> // acc = x + 1<..0..>
//    acc += x // acc = x + (x + 1<..0..>) = 1<..x[1:]..>
// }
// output: acc = 1<..x[1:]..> so it can be further compared with x to determine the value of the first bit
// side output: neg = -(old acc)

// reg2mem ver1 (inversed):
// requirement: env where mem[1] is a regular bit
// input: p, x
// side effects:
//  random modification of mem[1] bit
// output:
//  mem[p:p+&sizeofreg] = inversed reg x content
//  acc = @loop
//  magicN = 1<..0..>
//  pe = initial p + &sizeofreg
//  p = pe
//  x = 0
//  addr = 1
//  else = .end

acc = &sizeofreg
acc += p
pe = acc // pe = p + &sizeofreg

magicN = 1<..0..>

addr = 1

@loop // while (p != pe)
{
    // condition
    {
        // [assert addr = 1]
        // assuming env where mem[1] is a regular bit
        else = pe
        cond = p
        else = .end // note: modifies acc and neg
        ip = cond
    }

    // body
    {
        // store inverse of high bit at p:
        neg = -acc
        acc += neg // acc = 0
        acc += x // acc = x
        acc += magicN // acc = x + magicN
        acc += x // acc = x + (x + magicN) = 1<..x[1:]..>
        addr = p
        else = acc
        cond = x // write inversed high bit

        // move high bit
        acc += acc // acc = <..x[1:]..>0
        x = acc

        // increment p
        neg = -acc
        acc += neg // acc = 0
        acc += p // acc = p
        addr = 1
        acc += addr
        p = acc
    }

    ip := @loop // note: modifies acc and neg
}
@end