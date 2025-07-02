# ui_manager.py (完整版)
import framebuf
from machine import SPI, Pin
import time

class UIManager:
    def __init__(self, st7789_driver, default_text_color=None, default_bg_color=None, default_highlight_color=None):
        """
        初始化 UI 管理器 (完整适配 ESP32-S3)
        Args:
            st7789_driver: ST7789 驱动实例
            default_text_color: 默认文字颜色 (RGB565)
            default_bg_color: 默认背景颜色 (RGB565)
            default_highlight_color: 默认高亮颜色 (RGB565)
        """
        self.screen = st7789_driver
        self.width = self.screen.width
        self.height = self.screen.height

        # 颜色设置 (RGB565)
        self.text_color = default_text_color if default_text_color is not None else self.screen.WHITE
        self.bg_color = default_bg_color if default_bg_color is not None else self.screen.BLACK
        self.highlight_text_color = default_highlight_color if default_highlight_color is not None else self.screen.GREEN
        self.highlight_bg_color = self.screen.YELLOW

        # 字体参数
        self.char_width_eng = 8
        self.char_height = 16
        self.line_spacing = 4

        # 局部刷新状态记录
        self._last_menu_state = {
            'selected_idx': -1,
            'items': None,
            'start_y': 0
        }

    def clear_screen(self, color=None):
        """清屏"""
        self.screen.fill(color if color is not None else self.bg_color)

    def _draw_char_internal(self, char_code, x, y, color, bg_color):
        """绘制单个字符 (兼容ASCII)"""
        char = chr(char_code) if isinstance(char_code, int) and char_code < 128 else '?'
        if bg_color is not None:
            self.screen.fill_rect(x, y, self.char_width_eng, self.char_height, bg_color)
        self.screen.text(char, x, y, color)

    def display_text_line(self, text, x, y, text_color=None, bg_color=None, max_width=None):
        """
        绘制单行文本
        Args:
            max_width: 最大宽度（像素），超出部分截断
        """
        color = text_color if text_color is not None else self.text_color
        current_x = x
        for char in text:
            if max_width is not None and (current_x + self.char_width_eng) > (x + max_width):
                break
            self._draw_char_internal(ord(char), current_x, y, color, bg_color)
            current_x += self.char_width_eng
        return current_x

    def display_text_multiline(self, text, x, y, max_width, text_color=None, bg_color=None, line_height=None):
        """
        绘制多行文本（自动换行）
        Args:
            text: 完整文本字符串（自动按空格分词）
            line_height: 行高（像素）
        """
        color = text_color if text_color is not None else self.text_color
        actual_line_height = line_height if line_height is not None else (self.char_height + self.line_spacing)
        words = text.split(' ')
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) * self.char_width_eng <= max_width:
                current_line = test_line
            else:
                # 绘制当前行
                self.display_text_line(current_line, x, y, color, bg_color, max_width)
                y += actual_line_height
                if y + self.char_height > self.height:
                    return  # 超出屏幕底部
                current_line = word
        
        # 绘制最后一行
        if current_line:
            self.display_text_line(current_line, x, y, color, bg_color, max_width)

    def draw_menu(self, items, selected_index, title=None, start_y=10):
        last_state = self._last_menu_state
        need_full_refresh = (last_state['items'] != items or
                             last_state['start_y'] != start_y or
                             last_state.get('title_text') != title)
        title_height = 0
        if title:
            title_height = self.char_height + self.line_spacing
        
        if need_full_refresh:
            self.clear_screen()
            current_y = start_y
            if title:
                # 绘制标题（带背景色填充）
                self.screen.fill_rect(0, current_y, self.width, title_height, self.bg_color)
                self.display_text_multiline(title, 5, current_y, self.width - 10,
                                            self.highlight_text_color, self.bg_color)
                current_y += title_height
                # 绘制所有菜单项
                for i, item in enumerate(items):
                    self._draw_menu_item(i, item, start_y, title_height, i == selected_index)
        else:
            # 局部刷新：只更新变化的菜单项
            old_idx = last_state['selected_idx']
            if old_idx != selected_index:
                self._draw_menu_item(old_idx, items[old_idx], start_y, title_height, False)
                self._draw_menu_item(selected_index, items[selected_index], start_y, title_height, True)
                # 更新状态时需要记录标题信息
                self._last_menu_state = {
                    'selected_idx': selected_index,
                    'items': items,
                    'start_y': start_y,
                    'title_text': title
                }
    def _draw_menu_item(self, index, text, start_y, title_height, is_selected):
        """绘制单个菜单项（确保不会覆盖标题区域）"""
        # 计算菜单项位置（考虑标题高度）
        y_pos = start_y + title_height + index * (self.char_height + self.line_spacing * 2)
        # 只填充菜单项区域
        item_height = self.char_height + self.line_spacing
        self.screen.fill_rect(0, y_pos, self.width, item_height,
                              self.highlight_bg_color if is_selected else self.bg_color)
        # 绘制菜单文本
        text_color = self.highlight_text_color if is_selected else self.text_color
        self.display_text_line(text, 5, y_pos + self.line_spacing, text_color, None)

    def show_message_box(self, message_lines, title="tip", options=None, selected_option_index=0):
        """
        消息框（完整实现）
        """
        self.clear_screen()
        padding = 10
        box_height = self.height - 2 * padding
        current_y = padding

        # 绘制标题
        if title:
            self.display_text_multiline(title, padding, current_y, self.width - 2*padding,
                                      self.highlight_text_color, self.bg_color)
            current_y += self.char_height + self.line_spacing * 2

        # 绘制消息正文
        for line in message_lines:
            self.display_text_multiline(line, padding, current_y, self.width - 2*padding,
                                      self.text_color, self.bg_color)
            current_y += self.char_height + self.line_spacing
            if current_y > box_height - 20:  # 预留底部按钮空间
                break

        # 绘制底部按钮
        if options:
            button_spacing = 5
            button_width = (self.width - 2*padding - (len(options)-1)*button_spacing) // len(options)
            for i, option in enumerate(options):
                btn_x = padding + i * (button_width + button_spacing)
                is_selected = (i == selected_option_index)
                color = self.highlight_text_color if is_selected else self.text_color
                bg_color = self.highlight_bg_color if is_selected else self.bg_color
                
                # 按钮背景
                self.screen.fill_rect(btn_x, box_height - 25, button_width, 20, bg_color)
                # 按钮文字（居中）
                text_x = btn_x + (button_width - len(option)*self.char_width_eng) // 2
                self.display_text_line(option, text_x, box_height - 20, color, None)

    def show_welcome_screen(self):
        """欢迎界面"""
        self.clear_screen(self.screen.BLUE)  # 蓝色背景
        title = "Gambling bot"
        text_x = (self.width - len(title)*self.char_width_eng) // 2
        self.display_text_line(title, text_x, self.height//2 - 10, self.screen.YELLOW, None)  # 黄色文字
        self.display_text_line("Loading...", 10, self.height//2 + 10, self.screen.WHITE, None)  # 白色文字


