// hello world asm:

// volatile
reg4 = .msg // data pointer

// constants
reg0 = .msgend
reg1 = .loop
reg2 = 2
reg3 = 3

// as it used only in one place, can be defined once
regIf = .halt
regElse = .body

@.loop

// check pointer reached the end, jmp to halt if so
regSrc = reg0 // = .msgend
regIP = regCond
@.body

// stdout
regDst = reg2 // = 2
regSrc = reg4
regDst = regConst0
regSrc = regConst0
regDst = reg3 // = 3
regSrc = regConst1
// regSrc = regConst0 // usually needs, but regDst is modified rigth next, so no need

// mark bit
regDst = reg4
// regSrc = regConst1 optimized out, as it is surely = regConst1 at this point
regDst = regConst0

// advance data pointer
regA = reg4
regB = regConst1
reg4 = regSum

// jmp to loop
regIP = reg1  // = .loop

@.halt
regDst = regConst1
regSrc = regConst0

@.msg
#store_ascii "Hello World!\n"
@.msgend
#store 0xb0