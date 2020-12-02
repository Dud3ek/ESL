from pygmyhdl import *


@chunk
def debouncer(clk_i, button_i, button_o, debounce_time):
    '''
    Inputs:
        clk_i: Main clock input.
        button_i: Raw button input.
        button_o: Debounced button output.
        debounce_time: Number of clock cycles the button value has to be stable.
    '''

    # These are the state variables of the FSM.
    from math import ceil, log2
    debounce_cnt = Bus(int(ceil(log2(debounce_time + 1))), name='dbcnt')  # Counter big enough to store debounce time.
    prev_button = Wire(name='prev_button')  # Stores the button value from the previous clock cycle.

    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if button_i == prev_button:
            # If the current and previous button values are the same, decrement the counter
            # until it reaches zero and then stop.
            if debounce_cnt != 0:
                debounce_cnt.next = debounce_cnt - 1
        else:
            # If the current and previous button values aren't the same, then the button must
            # still be bouncing so reset the counter to the debounce interval and try again.
            debounce_cnt.next = debounce_time

        # Store the current button value for comparison during the next clock cycle.
        prev_button.next = button_i

    @seq_logic(clk_i.posedge)
    def output_logic():
        if debounce_cnt == 0:
            # Output the stable button value whenever the counter is zero.
            # Don't use the actual button input value because that could change at any time.
            button_o.next = prev_button


@chunk
def classic_fsm(clk_i, inputs_i, outputs_o):
    fsm_state = State('A', 'B', 'C', 'D', name='state')
    reset_cnt = Bus(2)

    prev_inputs = Bus(len(inputs_i), name='prev_inputs')
    input_chgs = Bus(len(inputs_i), name='input_chgs')

    # Take the inputs and run them through the debounce circuits.
    dbnc_inputs = Bus(len(inputs_i))  # These are the inputs after debouncing.
    debounce_time = 120000
    debouncer(clk_i, inputs_i.o[0], dbnc_inputs.i[0], debounce_time)
    debouncer(clk_i, inputs_i.o[1], dbnc_inputs.i[1], debounce_time)

    # The edge detection of the inputs is now performed on the debounced inputs.
    @comb_logic
    def detect_chg():
        input_chgs.next = dbnc_inputs & ~prev_inputs

    @seq_logic(clk_i.posedge)
    def next_state_logic():
        if reset_cnt < reset_cnt.max - 1:
            fsm_state.next = fsm_state.s.A
            reset_cnt.next = reset_cnt + 1
        elif fsm_state == fsm_state.s.A:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.B
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.D
        elif fsm_state == fsm_state.s.B:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.C
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.A
        elif fsm_state == fsm_state.s.C:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.D
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.B
        elif fsm_state == fsm_state.s.D:
            if input_chgs[0]:
                fsm_state.next = fsm_state.s.A
            elif input_chgs[1]:
                fsm_state.next = fsm_state.s.C
        else:
            fsm_state.next = fsm_state.s.A

        prev_inputs.next = dbnc_inputs  # Store the debounced inputs.

    @comb_logic
    def output_logic():
        if fsm_state == fsm_state.s.A:
            outputs_o.next = 0b0001
        elif fsm_state == fsm_state.s.B:
            outputs_o.next = 0b0010
        elif fsm_state == fsm_state.s.C:
            outputs_o.next = 0b0100
        elif fsm_state == fsm_state.s.D:
            outputs_o.next = 0b1000
        else:
            outputs_o.next = 0b1111


initialize()

inputs = Bus(2, name='inputs')
outputs = Bus(4, name='outputs')
clk = Wire(name='clk')
classic_fsm(clk, inputs, outputs)


def fsm_tb():
    nop = 0b00
    fwd = 0b01
    bck = 0b10

    ins = [nop, nop, nop, nop, fwd, fwd, fwd, bck, bck, bck]
    for inputs.next in ins:
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)

    # Interspersed active and inactive inputs.
    ins = [fwd, nop, fwd, nop, fwd, nop, bck, nop, bck, nop, bck, nop]
    for inputs.next in ins:
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)


simulate(fsm_tb())
show_text_table()

toVerilog(classic_fsm, clk_i=Wire(), inputs_i=Bus(2), outputs_o=Bus(4))
