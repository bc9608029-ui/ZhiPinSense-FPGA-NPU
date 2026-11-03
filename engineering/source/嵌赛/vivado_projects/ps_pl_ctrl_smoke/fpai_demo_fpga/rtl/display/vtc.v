module vtc(
    input           clk            ,      
    input           rst_n          ,  

    input  [31 : 0]  H_SYNC        ,
    input  [31 : 0]  H_BACK_PORCH  ,
    input  [31 : 0]  H_ACTIVE      ,
    input  [31 : 0]  H_FRONT_PORCH ,
    input  [31 : 0]  V_SYNC        ,
    input  [31 : 0]  V_BACK_PORCH  , 
    input  [31 : 0]  V_ACTIVE      ,
    input  [31 : 0]  V_FRONT_PORCH ,

    output [23 : 0]  data          ,
    output           vs            ,      
    output           hs            ,      
    output           de         	
);

    wire [31:0]hcnt_max;
    wire [31:0]vcnt_max;
    
    assign hcnt_max    = H_SYNC + H_BACK_PORCH + H_ACTIVE + H_FRONT_PORCH;     
    assign vcnt_max    = V_SYNC + V_BACK_PORCH + V_ACTIVE + V_FRONT_PORCH;     

    reg     [31:0]  hcnt        ;
    reg     [31:0]  vcnt        ;
    reg     [ 7:0]  frame_cnt   ;
    wire            hs_valid    ;
    wire            vs_valid    ;    

    //视频水平方向，列计数�?
    always @(posedge clk)begin
        if(rst_n == 1'b0) 
            hcnt <= 32'd0;
        else if(hcnt < (hcnt_max - 1'b1))
            hcnt <= hcnt + 1'b1;
        else 
            hcnt <= 32'd0;
    end         
    
    //视频垂直方向，行计数器，用于计数已经完成的行视频信号
    always @(posedge clk)begin
        if(rst_n == 1'b0)
            vcnt <= 32'd0;
        else if(hcnt == (hcnt_max - 1'b1)) begin
                if(vcnt == (vcnt_max - 1'b1))
                    vcnt <= 32'd0;
                else
                    vcnt <= vcnt + 1'b1;
        end
        else 
            vcnt <= vcnt;
    end 

    always @(posedge clk)begin
        if(rst_n == 1'b0) 
            frame_cnt <= 8'd0;
        else if((vcnt == 'd0) && (hcnt == 'd0))
            frame_cnt <= frame_cnt + 1'b1;
    end  

    assign hs_valid    =  ((hcnt >= H_SYNC +H_BACK_PORCH)&&(hcnt < H_SYNC +H_BACK_PORCH +H_ACTIVE))? 1'b1 : 1'b0; //行信号有效像素部�?
    assign vs_valid    =  ((vcnt >=V_SYNC + V_BACK_PORCH)&&(vcnt<V_SYNC+V_BACK_PORCH+V_ACTIVE))? 1'b1 : 1'b0; //场信号有效像素部�?
    assign hs  =  (hcnt < H_SYNC) ? 1'b1 : 1'b0;//产生hs，行同步信号
    assign vs  =  (vcnt < V_SYNC) ? 1'b1 : 1'b0;//产生vs，场同步信号      
    assign de  =  hs_valid && vs_valid;//只有当视频水平方向，列有效和视频垂直方向，行同时有效，视频数据部分才是有�?
    assign data = de ? {3{hcnt[7:0]+frame_cnt[7:0]}} : 'd0;

endmodule

