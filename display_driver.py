import machine
import time
import ustruct as struct
from machine import Pin, SPI

from framebuf import FrameBuffer, MONO_HLSB # 导入 FrameBuffer 和 MONO_HLSB 模式

class ST7789:
    # 命令常量
    NOP = 0x00
    SWRESET = 0x01
    RDDID = 0x04
    RDDST = 0x09
    SLPIN = 0x10
    SLPOUT = 0x11
    PTLON = 0x12
    NORON = 0x13
    INVOFF = 0x20
    INVON = 0x21
    DISPOFF = 0x28
    DISPON = 0x29
    CASET = 0x2A
    RASET = 0x2B
    RAMWR = 0x2C
    RAMRD = 0x2E
    PTLAR = 0x30
    COLMOD = 0x3A
    MADCTL = 0x36
    
    # 颜色定义 (RGB565)
    WHITE = 0x0000
    YELLOW = 0x001F
    CYAN = 0xF800
    MAGENTA = 0x07E0
    RED = 0x07FF
    GREEN = 0xF81F
    BLUE = 0xFFE0
    BLACK = 0xFFFF
    # 精简版字体数据（仅包含数字和大小写字母）
    # 空格 (ASCII 32)
    
    
    def __init__(self, spi, width, height, reset=None, dc=None, cs=None, backlight=None, rotation=0):
        """
        初始化ST7789显示屏
        参数:
            spi: SPI接口对象
            width: 屏幕宽度
            height: 屏幕高度
            reset: 复位引脚
            dc: 数据/命令选择引脚
            cs: 片选引脚
            backlight: 背光控制引脚
            rotation: 屏幕旋转方向 (0-3)
        """
        self.spi = spi
        self.width = width
        self.height = height
        self.reset_pin = reset
        self.dc_pin = dc
        self.cs_pin = cs
        self.bl_pin = backlight
        self.rotation = rotation % 4
        
        # 初始化GPIO
        if self.reset_pin:
            self.reset_pin.init(Pin.OUT, value=1)
        if self.dc_pin:
            self.dc_pin.init(Pin.OUT, value=0)
        if self.cs_pin:
            self.cs_pin.init(Pin.OUT, value=1)
        if self.bl_pin:
            self.bl_pin.init(Pin.OUT, value=1)
        
        # 硬件复位
        self.reset()
        
        # 发送初始化命令
        self._write_command(self.SWRESET)
        time.sleep_ms(150)
        self._write_command(self.SLPOUT)
        time.sleep_ms(255)
        
        # 配置颜色模式 (16位RGB565)
        self._write_command(self.COLMOD, bytearray([0x55]))
        
        # 设置显示方向
        self._write_command(self.MADCTL, bytearray([self._get_madctl()]))
        
        # 关闭睡眠模式
        self._write_command(self.DISPON)
        time.sleep_ms(100)
        
        # 清屏
        self.fill(self.BLACK)
    
    def reset(self):
        """执行硬件复位"""
        if self.reset_pin:
            self.reset_pin(1)
            time.sleep_ms(100)
            self.reset_pin(0)
            time.sleep_ms(100)
            self.reset_pin(1)
            time.sleep_ms(200)
    
    def _get_madctl(self):
        """根据旋转方向获取MADCTL值"""
        if self.rotation == 0:
            return 0x00
        elif self.rotation == 1:
            return 0x60
        elif self.rotation == 2:
            return 0xC0
        else:
            return 0xA0
    
    def _write_command(self, command, data=None):
        """写入命令到显示屏"""
        if self.dc_pin:
            self.dc_pin(0)
        if self.cs_pin:
            self.cs_pin(0)
        
        self.spi.write(bytearray([command]))
        
        if self.cs_pin:
            self.cs_pin(1)
        
        if data is not None:
            self._write_data(data)
    
    def _write_data(self, data):
        """写入数据到显示屏"""
        if self.dc_pin:
            self.dc_pin(1)
        if self.cs_pin:
            self.cs_pin(0)
        
        self.spi.write(data)
        
        if self.cs_pin:
            self.cs_pin(1)
    
    def set_window(self, x0, y0, x1, y1):
        """设置显示窗口"""
        # 根据旋转调整坐标
        if self.rotation in (1, 3):
            x0, y0 = y0, x0
            x1, y1 = y1, x1
        
        self._write_command(self.CASET, struct.pack(">HH", x0, x1))
        self._write_command(self.RASET, struct.pack(">HH", y0, y1))
        self._write_command(self.RAMWR)
    
    def pixel(self, x, y, color):
        """绘制单个像素"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.set_window(x, y, x, y)
            self._write_data(struct.pack(">H", color))
    
    def fill(self, color):
        """填充整个屏幕"""
        self.fill_rect(0, 0, self.width, self.height, color)
    
    def fill_rect(self, x, y, width, height, color):
        """填充矩形区域"""
        x_end = min(x + width - 1, self.width - 1)
        y_end = min(y + height - 1, self.height - 1)
        
        self.set_window(x, y, x_end, y_end)
        
        # 准备颜色数据
        pixel_data = struct.pack(">H", color)
        pixels = width * height
        chunk_size = 512  # 每次发送的像素数
        
        # 分块发送数据以避免内存不足
        for _ in range(0, pixels, chunk_size):
            self._write_data(pixel_data * min(chunk_size, pixels))
            pixels -= chunk_size
    def text(self, text_string, x, y, text_color, bg_color=None, font_height=16):
            """
            在指定位置显示一行文本，仅支持英文/ASCII字符。
            一次性绘制到内存缓冲区，再传输到屏幕。
            Args:
                text_string (str): 要显示的文本 (仅限ASCII)。
                x (int): 起始 x 坐标。
                y (int): 起始 y 坐标。
                text_color (int): 文字颜色 (RGB565)。
                bg_color (int, optional): 背景颜色 (RGB565)。如果为 None，则背景透明。
                font_height (int): 字体高度 (framebuf.text 会缩放，建议是 8 的倍数)。
            """
            # --- 1. 计算文本区域尺寸 ---
            # framebuf.text 默认的字体是 8x8。如果 font_height=16，则实际绘制尺寸是 16x16
            # 我们可以根据 font_height 来估算字符宽度
            char_width = font_height // 2 if font_height >= 8 else 8 # 假设一个字符宽度是高度的一半，至少8
            text_pixel_width = len(text_string) * char_width

            # 确保绘制区域在屏幕范围内
            x_end = min(x + text_pixel_width, self.width)
            y_end = min(y + font_height, self.height)
            
            draw_width = x_end - x
            draw_height = y_end - y

            if draw_width <= 0 or draw_height <= 0: # 区域无效
                return

            # --- 2. 在内存中创建 FrameBuffer 并绘制文本 ---
            # fb_buf_size: (宽度按8位对齐) * 高度
            fb_buf_size = (draw_width + 7) // 8 * draw_height
            fb_buf = bytearray(fb_buf_size)
            fb = FrameBuffer(fb_buf, draw_width, draw_height, MONO_HLSB)
            
            # 填充内存缓冲区：如果背景是透明，就用0填充；如果指定了背景色，也用0填充（因为是单色模式）
            fb.fill(0) 

            # 绘制文本到内存缓冲区
            # fb.text(string, x_on_buffer, y_on_buffer, color_on_buffer)
            # color_on_buffer 1表示前景色（文字），0表示背景色
            fb.text(text_string, 0, 0, 1) # 文字颜色设为 FrameBuffer 的前景色（1）

            # --- 3. 设置屏幕显示窗口 ---
            self.set_window(x, y, x_end - 1, y_end - 1)

            # --- 4. 将 FrameBuffer 数据转换为 RGB565 字节流并一次性发送 ---
            pixel_data_buffer = bytearray(draw_width * draw_height * 2) # 每像素 2 字节 (RGB565)
            idx = 0
            for py in range(draw_height):
                for px in range(draw_width):
                    # 检查 FrameBuffer 中的像素是否被设置 (文字部分)
                    is_pixel_set = (fb.pixel(px, py) == 1)
                    
                    # 确定最终像素颜色
                    # 如果是文字像素，用 text_color；否则，如果指定了 bg_color，用 bg_color，否则用屏幕默认的黑
                    target_color = text_color if is_pixel_set else (bg_color if bg_color is not None else self.BLACK)
                    
                    # 将 RGB565 颜色（一个整数）拆分为两个字节
                    pixel_data_buffer[idx] = (target_color >> 8) & 0xFF # 高字节
                    pixel_data_buffer[idx+1] = target_color & 0xFF      # 低字节
                    idx += 2
            
            # 一次性发送所有像素数据，这将大大减少 SPI 事务开销
            self._write_data(pixel_data_buffer)

    def char(self, char,x, y, color, bg_color, font_size=16):
        # 使用内置的8x8字体 (MicroPython内置字体)
        from framebuf import FrameBuffer, MONO_HLSB
        buf = bytearray(font_size * ((font_size + 7) // 8))
        fbuf = FrameBuffer(buf, font_size, font_size, MONO_HLSB)
        
        fbuf.fill(0 if bg_color is not None else 0xFFFF)
        fbuf.text(char, 0, 0)
        
        for yy in range(font_size):
            for xx in range(font_size):
                if buf[yy * ((font_size + 7) // 8) + xx // 8] & (1 << (7 - xx % 8)):
                    self.pixel(x + xx, y + yy, color)
                elif bg_color is not None:
                    self.pixel(x + xx, y + yy, bg_color)

        
    def show(self):
        """更新显示 (兼容性方法)"""
        pass  # ST7789不需要显式刷新
    
    def backlight(self, value):
        """控制背光"""
        if self.bl_pin:
            self.bl_pin(value)
