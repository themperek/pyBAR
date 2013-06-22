`timescale 1ps / 1ps
`default_nettype none

module top (
    
    input wire FCLK_IN, // 48MHz
    
    //full speed 
    inout wire [7:0] DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FDATA,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //debug ports
    output wire [15:0] DEBUG_D,
    output wire [10:0] MULTI_IO, // Pin 1-11, 12: not connected, 13, 15: DGND, 14, 16: VCC_3.3V
    
    //LED
    output wire LED1,
    output wire LED2,
    output wire LED3,
    output wire LED4,
    output wire LED5,
    
    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,
    
    input wire [2:0] LEMO_RX,
    output wire [2:0] TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,
    
    output wire CMD_CLK,
    output wire CMD_DATA,
    output wire EN_V1, // EN_VA1 on SCC, EN_VDD1 on BIC
    output wire EN_V2, // EN_VA2 on SCC, EN_VDD2 on BIC
    output wire EN_V3, // EN_VD2 on SCC, EN_VDD3 on BIC
    output wire EN_V4, // EN_VD1 on SCC, EN_VDD4 on BIC
    
    input wire DOBOUT1, // BIC only
    input wire DOBOUT2, // BIC only
    input wire DOBOUT3, // BIC only
    input wire DOBOUT4, // DO on SCC
    
    // Over Current Protection (BIC only)
    input wire OC1,
    input wire OC2,
    input wire OC3,
    input wire OC4,
    
    // Select (SEL) LED (BIC only)
    output wire SEL1,
    output wire SEL2,
    output wire SEL3,
    output wire SEL4
    
    //input wire FPGA_BUTTON // switch S2 on MultiIO board, active low
);

wire BUS_RST;
wire BUS_CLK;
wire BUS_CLK270;
wire CLK_40;
wire RX_CLK;
wire RX_CLK90;
wire DATA_CLK;
wire CLK_LOCKED;

assign EN_V1 = 1'b1;
assign EN_V2 = 1'b1;
assign EN_V3 = 1'b1;
assign EN_V4 = 1'b1;

assign SEL1 = 1'b1;
assign SEL2 = 1'b1;
assign SEL3 = 1'b1;
assign SEL4 = 1'b1;

wire [10:0] fei4_rx_d;
assign MULTI_IO = fei4_rx_d;//11'b000_0000_0000;
assign DEBUG_D = 16'ha5a5;

// 1Hz CLK
wire CE_1HZ; // use for sequential logic
wire CLK_1HZ; // don't connect to clock input, only combinatorial logic

clock_divider #(
    .DIVISOR(40000000)
) clock_divisor_40MHz_to_1Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE(CE_1HZ),
    .CLOCK(CLK_1HZ)
);

// Trigger
wire CMD_EXT_START_FLAG;
wire CMD_EXT_START_ENABLE;

wire LEMO_TRIGGER, LEMO_RESET, EXT_VETO;
assign LEMO_TRIGGER = LEMO_RX[0];
assign LEMO_RESET = LEMO_RX[1];
assign EXT_VETO = LEMO_RX[2];

// TLU
wire            RJ45_ENABLED;
wire            TLU_BUSY;                   // busy signal to TLU to deassert trigger
wire            TLU_CLOCK;
wire            CMD_READY;

assign TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign TX[1] = TLU_BUSY; // in TLU handshake mode TLU_BUSY signal; also connected to RJ45 output
assign TX[2] = (RJ45_ENABLED == 1'b1) ? RJ45_TRIGGER : LEMO_TRIGGER;

// LED
parameter VERSION = 3; // all on: 31

wire RX_READY, RX_ERR;
wire FIFO_NOT_EMPTY; // raised, when SRAM FIFO is not empty
wire FIFO_FULL; // raised, when SRAM FIFO is full
wire FIFO_READ_ERROR; // raised, when attempting to read from SRAM FIFO when it is empty
wire RX_FIFO_FULL; // raised, when RX FIFO full
reg FIFO_NEAR_FULL;
always @ (posedge BUS_CLK)
begin
    if (RX_READY == 1'b0 || FIFO_FULL == 1'b1 || RX_FIFO_FULL == 1'b1)
        FIFO_NEAR_FULL <= 1'b1;
    else
        FIFO_NEAR_FULL <= 1'b0;
end

wire SHOW_VERSION;

SRLC16E # (
    .INIT(16'hF000) // in seconds, MSB shifted first
) SRLC16E_LED (
    .Q(SHOW_VERSION),
    .Q15(),
    .A0(1'b1),
    .A1(1'b1),
    .A2(1'b1),
    .A3(1'b1),
    .CE(CE_1HZ),
    .CLK(CLK_40),
    .D(1'b0)
);

// LED assignments
assign LED1 = SHOW_VERSION? VERSION[0] : CLK_1HZ & CLK_LOCKED;
assign LED2 = SHOW_VERSION? VERSION[1] : RX_READY & (CLK_1HZ | ~RX_ERR); // blink when RX_ERR, off when no RX_READY, on when everything is OK
assign LED3 = SHOW_VERSION? VERSION[2] : (FIFO_FULL == 1'b1 || RX_FIFO_FULL == 1'b1);
assign LED4 = SHOW_VERSION? VERSION[3] : FIFO_READ_ERROR;
assign LED5 = SHOW_VERSION? VERSION[4] : RJ45_ENABLED;

reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

clk_gen iclkgen(
    .U1_CLKIN_IN(FCLK_IN), 
    .U1_RST_IN(1'b0),  
    .U1_CLKIN_IBUFG_OUT(), 
    .U1_CLK0_OUT(BUS_CLK), 
    .U1_CLK270_OUT(BUS_CLK270), 
    .U1_STATUS_OUT(), 
    .U2_CLKFX_OUT(CLK_40),
    .U2_CLKDV_OUT(DATA_CLK),
    .U2_CLK0_OUT(RX_CLK), 
    .U2_CLK90_OUT(RX_CLK90),
    .U2_LOCKED_OUT(CLK_LOCKED),
    .U2_STATUS_OUT()
);

wire [7:0] BUS_DATA_IN;
assign BUS_DATA_IN = DATA;

reg [7:0] DATA_OUT;

reg [15:0] CMD_ADD;
wire [7:0] CMD_BUS_DATA_OUT;
reg CMD_BUS_RD, CMD_BUS_WR;

reg [15:0] RX_ADD;
wire [7:0] RX_BUS_DATA_OUT;
reg RX_BUS_RD, RX_BUS_WR;

reg [15:0] FIFO_ADD;
wire [7:0] FIFO_BUS_DATA_OUT;
reg FIFO_RD, FIFO_WR;

reg [15:0] TLU_ADD;
wire [7:0] TLU_BUS_DATA_OUT;
reg TLU_RD, TLU_WR;

wire [15:0] ADD_REAL;
assign ADD_REAL = ADD - 16'h4000;

always@ (*) begin
    DATA_OUT = 0;
    
    CMD_ADD = 0;
    CMD_BUS_RD = 0;
    CMD_BUS_WR = 0;
    
    RX_BUS_RD = 0;
    RX_BUS_WR = 0;
    RX_ADD = 0;
    
    FIFO_ADD = 0;
    FIFO_RD = 0;
    FIFO_WR = 0;
    
    TLU_ADD = 0;
    TLU_RD = 0;
    TLU_WR = 0;
    
    if( ADD_REAL < 16'h8000 ) begin
        CMD_BUS_RD = ~RD_B;
        CMD_BUS_WR = ~WR_B;
        CMD_ADD = ADD_REAL;
        DATA_OUT = CMD_BUS_DATA_OUT;
    end
    else if( ADD_REAL < 16'h8100 ) begin
        RX_BUS_RD = ~RD_B;
        RX_BUS_WR = ~WR_B;
        RX_ADD = ADD_REAL-16'h8000;
        DATA_OUT = RX_BUS_DATA_OUT;
    end
    else if( ADD_REAL < 16'h8200 ) begin
        FIFO_RD = ~RD_B;
        FIFO_WR = ~WR_B;
        FIFO_ADD = ADD_REAL-16'h8100;
        DATA_OUT = FIFO_BUS_DATA_OUT;
    end
    else if( ADD_REAL < 16'h8300 ) begin
        TLU_RD = ~RD_B;
        TLU_WR = ~WR_B;
        TLU_ADD = ADD_REAL-16'h8200;
        DATA_OUT = TLU_BUS_DATA_OUT;
    end
end

assign DATA = ~RD_B ? DATA_OUT : 8'bzzzz_zzzz;

cmd_seq icmd
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(CMD_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(CMD_BUS_RD),
    .BUS_WR(CMD_BUS_WR),
    .BUS_DATA_OUT(CMD_BUS_DATA_OUT),
    
    .CMD_CLK_OUT(CMD_CLK),
    .CMD_CLK_IN(CLK_40),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    .CMD_DATA(CMD_DATA),
    .CMD_READY(CMD_READY)
);

wire            FIFO_READ;
wire            FIFO_EMPTY;
wire    [31:0]  FIFO_DATA;

wire            FE_FIFO_READ;
wire            FE_FIFO_EMPTY;
wire    [31:0]  FE_FIFO_DATA;

wire            TLU_FIFO_READ;
wire            TLU_FIFO_EMPTY;
wire    [31:0]  TLU_FIFO_DATA;

// FIFO
reg TLU_FIFO_ACCESS;
initial TLU_FIFO_ACCESS = 1'b0;
always @ (posedge BUS_CLK)
begin
    if (TLU_FIFO_ACCESS == 1'b0 && TLU_FIFO_EMPTY == 1'b1) // default
        TLU_FIFO_ACCESS <= 1'b0;
    else if (TLU_FIFO_ACCESS == 1'b1 && TLU_FIFO_READ == 1'b1) // de-assert after successful writing
        TLU_FIFO_ACCESS <= 1'b0;
    else if (TLU_FIFO_EMPTY == 1'b0 && (FE_FIFO_EMPTY == 1'b1 || FE_FIFO_READ == 1'b1)) // assert if bus is free or directly after FE FIFO access
        TLU_FIFO_ACCESS <= 1'b1;
    else
        TLU_FIFO_ACCESS <= TLU_FIFO_ACCESS;
end

assign FE_FIFO_READ = (TLU_FIFO_ACCESS == 1'b0) ? FIFO_READ : 1'b0;
assign TLU_FIFO_READ = (TLU_FIFO_ACCESS == 1'b1) ? FIFO_READ : 1'b0;
assign FIFO_EMPTY = (TLU_FIFO_ACCESS == 1'b1) ? TLU_FIFO_EMPTY : FE_FIFO_EMPTY;
assign FIFO_DATA = (TLU_FIFO_ACCESS == 1'b1) ? TLU_FIFO_DATA : FE_FIFO_DATA;


wire USB_READ;
assign USB_READ = FREAD & FSTROBE;

out_fifo iout_fifo
(
    .BUS_CLK(BUS_CLK),
    .BUS_CLK270(BUS_CLK270),
    .BUS_RST(BUS_RST),
    .BUS_ADD(FIFO_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(FIFO_RD),
    .BUS_WR(FIFO_WR),
    .BUS_DATA_OUT(FIFO_BUS_DATA_OUT),
    
    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),
    
    .USB_READ(USB_READ),
    .USB_DATA(FDATA),
    
    .FIFO_READ_NEXT_OUT(FIFO_READ),
    .FIFO_EMPTY_IN(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA),
    
    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);

parameter DSIZE = 10;
//parameter CLKIN_PERIOD = 6.250;

fei4_rx #(
    .DSIZE(DSIZE)
//    .CLKIN_PERIOD(CLKIN_PERIOD)
) ifei4_rx (
    .RX_CLK(RX_CLK),
    .RX_CLK90(RX_CLK90),
    .DATA_CLK(DATA_CLK),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(DOBOUT4),
    
    .RX_READY(RX_READY),
    .RX_ERR(RX_ERR),
     
    .FIFO_READ(FE_FIFO_READ),
    .FIFO_EMPTY(FE_FIFO_EMPTY),
    .FIFO_DATA(FE_FIFO_DATA),
    
    .RX_FIFO_FULL(RX_FIFO_FULL),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR),
    .BUS_RD(RX_BUS_RD),
    
    .fei4_rx_d(fei4_rx_d)
);

tlu_controller #(
    .DIVISOR(12)
) tlu_controller_module (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(TLU_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(TLU_RD),
    .BUS_WR(TLU_WR),
    .BUS_DATA_OUT(TLU_BUS_DATA_OUT),
    
    .CMD_CLK(CLK_40),
    
    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),
    
    .RJ45_TRIGGER(RJ45_TRIGGER),
    .LEMO_TRIGGER(LEMO_TRIGGER),
    .RJ45_RESET(RJ45_RESET),
    .LEMO_RESET(LEMO_RESET),
    .RJ45_ENABLED(RJ45_ENABLED),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .EXT_VETO(EXT_VETO),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),

    .FIFO_NEAR_FULL(FIFO_NEAR_FULL)
);

// Chipscope
`ifdef SYNTHESIS_NOT
//`ifdef SYNTHESIS
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
);

chipscope_ila ichipscope_ila
(
    .CONTROL(control_bus),
    .CLK(CLK_160),
    .TRIG0({FIFO_DATA[23:0], TLU_BUSY, TLU_FIFO_EMPTY, TLU_FIFO_READ, FE_FIFO_EMPTY, FE_FIFO_READ, TLU_FIFO_ACCESS, FIFO_EMPTY, FIFO_READ})
    //.CLK(CLK_160),
    //.TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, DOBOUT4 ,WR_B, RD_B})
);
`endif


endmodule
