from pygmyhdl import *


@chunk
def ram(clk_i, wr_i, addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:  Data is read/written on the rising edge of this clock input.
      wr_i:   When high, data is written to the RAM; when low, data is read from the RAM.
      addr_i: Address bus for selecting which RAM location is being read/written.
      data_i: Data bus for writing data into the RAM.
    Outputs:
      data_o: Data bus for reading data from the RAM.
    '''

    mem = [Bus(len(data_i)) for _ in range(2 ** len(addr_i))]

    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[addr_i.val].next = data_i
        else:
            data_o.next = mem[addr_i.val]


toVerilog(ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(8), data_i=Bus(8), data_o=Bus(8))


@chunk
def simpler_ram(clk_i, wr_i, addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:  Data is read/written on the rising edge of this clock input.
      wr_i:   When high, data is written to the RAM; when low, data is read from the RAM.
      addr_i: Address bus for selecting which RAM location is being read/written.
      data_i: Data bus for writing data into the RAM.
    Outputs:
      data_o: Data bus for reading data from the RAM.
    '''

    mem = [Bus(len(data_i)) for _ in range(2 ** len(addr_i))]

    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[addr_i.val].next = data_i
        data_o.next = mem[addr_i.val]  # RAM address is always read out!


toVerilog(simpler_ram, clk_i=Wire(), wr_i=Wire(), addr_i=Bus(8), data_i=Bus(8), data_o=Bus(8))


@chunk
def dualport_ram(clk_i, wr_i, wr_addr_i, rd_addr_i, data_i, data_o):
    '''
    Inputs:
      clk_i:     Data is read/written on the rising edge of this clock input.
      wr_i:      When high, data is written to the RAM; when low, data is read from the RAM.
      wr_addr_i: Address bus for selecting which RAM location is being written.
      rd_addr_i: Address bus for selecting which RAM location is being read.
      data_i:    Data bus for writing data into the RAM.
    Outputs:
      data_o:    Data bus for reading data from the RAM.
    '''

    mem = [Bus(len(data_i)) for _ in range(2 ** len(wr_addr_i))]

    @seq_logic(clk_i.posedge)
    def logic():
        if wr_i:
            mem[wr_addr_i.val].next = data_i
        data_o.next = mem[rd_addr_i.val]  # Read from a different location than write.


initialize()

# Create wires and buses to connect to the dual-port RAM.
clk = Wire(name='clk')
wr = Wire(name='wr')
wr_addr = Bus(8, name='wr_addr')  # Address bus for writes.
rd_addr = Bus(8, name='rd_addr')  # Second address bus for reads.
data_i = Bus(8, name='data_i')
data_o = Bus(8, name='data_o')

# Instantiate the RAM.
dualport_ram(clk_i=clk, wr_i=wr, wr_addr_i=wr_addr, rd_addr_i=rd_addr, data_i=data_i, data_o=data_o)


def ram_test_bench():
    for i in range(10):  # Perform 10 RAM writes and reads.

        # Write data to address i.
        wr_addr.next = i
        data_i.next = 3 * i + 1
        wr.next = 1

        # Read data from address i-3. After three clocks, the data that entered
        # on the data_i bus will start to appear on the data_o bus.
        rd_addr.next = i - 3

        # Pulse the clock to trigger the write and read operations.
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)


# Simulate the RAM using the test bench.
simulate(ram_test_bench())


@chunk
def gen_reset(clk_i, reset_o):
    '''
    Generate a reset pulse to initialize everything.
    Inputs:
        clk_i:   Input clock.
    Outputs:
        reset_o: Active-high reset pulse.
    '''
    cntr = Bus(1)  # Reset counter.

    @seq_logic(clk_i.posedge)
    def logic():
        if cntr < 1:
            # Generate a reset while the counter is less than some threshold
            # and increment the counter.
            cntr.next = cntr.next + 1
            reset_o.next = 1
        else:
            # Release the reset once the counter passes the threshold and
            # stop incrementing the counter.
            reset_o.next = 0


@chunk
def sample_en(clk_i, do_sample_o, frq_in=12e6, frq_sample=100):
    '''
    Send out a pulse every so often to trigger a sampling operation.
    Inputs:
        clk_i:      Input clock.
        frq_in:     Frequency of the input clock (defaults to 12 MHz).
        frq_sample: Frequency of the sample clock (defaults to 100 Hz).
    Outputs:
        do_sample_o: Sends out a single-cycle pulse every 1/frq_sample seconds.
    '''
    # Compute the width of the counter and when it should roll-over based
    # on the master clock frequency and the desired sampling frequency.
    from math import ceil, log2
    rollover = int(ceil(frq_in / frq_sample)) - 1
    cntr = Bus(int(ceil(log2(frq_in / frq_sample))))

    # Sequential logic for generating the sampling pulse.
    @seq_logic(clk_i.posedge)
    def counter():
        cntr.next = cntr + 1  # Increment the counter.
        do_sample_o.next = 0  # Clear the sampling pulse output except...
        if cntr == rollover:
            do_sample_o.next = 1  # ...when the counter rolls over.
            cntr.next = 0


@chunk
def record_play(clk_i, button_a, button_b, leds_o):
    '''
    Sample value on button B input, store in RAM, and playback by turning LEDs on/off.
    Inputs:
        clk_i:    Clock input.
        button_a: Button A input. High when pressed. Controls record/play operation.
        button_b: Button B input. High when pressed. Used to input samples for controlling LEDs.
    Outputs:
        leds_o:   LED outputs.
    '''

    # Instantiate the reset generator.
    reset = Wire()
    gen_reset(clk_i, reset)

    # Instantiate the sampling pulse generator.
    do_sample = Wire()
    sample_en(clk_i, do_sample)

    # Instantiate a RAM for holding the samples.
    wr = Wire()
    addr = Bus(11)
    end_addr = Bus(len(addr))  # Holds the last address of the recorded samples.
    data_i = Bus(1)
    data_o = Bus(1)
    ram(clk_i, wr, addr, data_i, data_o)

    # States of the record/playback controller.
    state = Bus(3)  # Holds the current state of the controller.
    INIT = 0  # Initialize. The reset pulse sends us here.
    WAITING_TO_RECORD = 1  # Getting read to record samples.
    RECORDING = 2  # Actually storing samples in RAM.
    WAITING_TO_PLAY = 3  # Getting ready to play back samples.
    PLAYING = 4  # Actually playing back samples.

    # Sequential logic for the record/playback controller.
    @seq_logic(clk_i.posedge)
    def fsm():

        wr.next = 0  # Keep the RAM write-control off by default.

        if reset:  # Initialize the controller using the pulse from the reset generator.
            state.next = INIT  # Go to the INIT state after the reset is released.

        elif do_sample:  # Process a sample whenever the sampling pulse arrives.

            if state == INIT:  # Initialize the controller.
                leds_o.next = 0b10101  # Light LEDs to indicate the INIT state.
                if button_a == 1:
                    # Get ready to start recording when button A is pressed.
                    state.next = WAITING_TO_RECORD  # Go to record setup state.

            elif state == WAITING_TO_RECORD:  # Setup for recording.
                leds_o.next = 0b11010  # Light LEDs to indicate this state.
                if button_a == 0:
                    # Start recording once button A is released.
                    addr.next = 0  # Start recording from beginning of RAM.
                    data_i.next = button_b  # Record the state of button B.
                    wr.next = 1  # Write button B state to RAM.
                    state.next = RECORDING  # Go to recording state.

            elif state == RECORDING:  # Record samples of button B to RAM.
                addr.next = addr + 1  # Next location for storing sample.
                data_i.next = button_b  # Sample state of button B.
                wr.next = 1  # Write button B state to RAM.
                # For feedback to the user, display the state of button B on the LEDs.
                leds_o.next = concat(1, button_b, button_b, button_b, button_b)
                if button_a == 1:
                    # If button A pressed, then get ready to play back the stored samples.
                    end_addr.next = addr + 1  # Store the last sample address.
                    state.next = WAITING_TO_PLAY  # Go to playback setup state.

            elif state == WAITING_TO_PLAY:  # Setup for playback.
                leds_o.next = 0b10000  # Light LEDs to indicate this state.
                if button_a == 0:
                    # Start playback once button A is released.
                    addr.next = 0  # Start playback from beginning of RAM.
                    state.next = PLAYING  # Go to playback state.

            elif state == PLAYING:  # Show recorded state of button B on the LEDs.
                leds_o.next = concat(1, data_o[0], data_o[0], data_o[0], data_o[0])
                addr.next = addr + 1  # Advance to the next sample.
                if addr == end_addr:
                    # Loop back to the start of RAM if this is the last sample.
                    addr.next = 0
                if button_a == 1:
                    # Record a new sample if button A is pressed.
                    state.next = WAITING_TO_RECORD

toVerilog(record_play, clk_i=Wire(), button_a=Wire(), button_b=Wire(), leds_o=Bus(5))
