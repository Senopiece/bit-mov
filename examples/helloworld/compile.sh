# just invoke ./compile.sh to get helloworld.ram.sim and helloworld.asm.sim
# then you can pass .ram to the ram of the computer and .asm to the rom of the computer

endmsg=$(python datagen.py helloworld.ram "Hello World!")
echo "RAM in use: $endmsg bit"
./asm 4 8 helloworld.asm sim --aug-msgend="$endmsg" --debug
