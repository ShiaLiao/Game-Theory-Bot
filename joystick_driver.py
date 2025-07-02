# joystick_driver.py
from machine import Pin, ADC
import time

class Joystick:
    def __init__(self, x_pin_num, y_pin_num, button_pin_num,
                 x_center=2048, y_center=2048, threshold=800,
                 debounce_ms=50, click_threshold_ms=300): # click_threshold_ms 用于区分长按和短按（如果需要）
        """
        初始化摇杆驱动。
        Args:
            x_pin_num (int): 连接摇杆 X 轴的 ADC 引脚号。
            y_pin_num (int): 连接摇杆 Y 轴的 ADC 引脚号。
            button_pin_num (int): 连接摇杆按钮的 GPIO 引脚号。
            x_center (int): X 轴中心ADC读数值 (校准后)。
            y_center (int): Y 轴中心ADC读数值 (校准后)。
            threshold (int): 触发方向判断的阈值。
            debounce_ms (int): 按钮防抖时间 (毫秒)。
            click_threshold_ms (int): 单击事件的最大持续时间 (毫秒)。
        """
        self.adc_x = ADC(Pin(x_pin_num))
        self.adc_y = ADC(Pin(y_pin_num))
        self.button = Pin(button_pin_num, Pin.IN, Pin.PULL_UP) # 假设按钮按下为低电平，使用上拉电阻

        # 配置 ADC (与崔提供的代码一致)
        self.adc_x.atten(ADC.ATTN_11DB)  # 满量程 3.3V
        self.adc_y.atten(ADC.ATTN_11DB)
        self.adc_x.width(ADC.WIDTH_12BIT) # 12位分辨率 (0-4095)
        self.adc_y.width(ADC.WIDTH_12BIT)

        self.x_center = x_center
        self.y_center = y_center
        self.threshold = threshold

        # 按钮状态管理
        self.debounce_ms = debounce_ms
        self.click_threshold_ms = click_threshold_ms
        self._last_button_state = self.button.value() # 初始按钮状态
        self._last_button_change_time = time.ticks_ms() # 上次按钮状态改变时间
        self._button_pressed_since_last_check = False # 用于 is_button_clicked_once
        self._button_down_start_time = 0 # 按钮按下的起始时间

        # 方向状态管理 (用于避免重复触发方向事件)
        self._last_direction = 'center'
        self._last_direction_time = time.ticks_ms()
        self.direction_repeat_delay_ms = 150 # 相同方向重复触发的最小延迟

    def get_raw_values(self):
        """返回摇杆 X 和 Y 轴的原始 ADC 读数。"""
        return self.adc_x.read(), self.adc_y.read()

    def get_direction(self, allow_repeat=False):
        """
        获取当前摇杆的方向。
        Args:
            allow_repeat (bool): 是否允许在摇杆保持在某个方向时重复返回该方向。
                                如果为 False，则只有方向改变时才返回新方向，否则返回 'center'。
        Returns:
            str: 'up', 'down', 'left', 'right', 'center'。
        """
        x_val = self.adc_x.read()
        y_val = self.adc_y.read()
        current_direction = 'center'

        if x_val > self.x_center + self.threshold:
            current_direction = 'right'
        elif x_val < self.x_center - self.threshold:
            current_direction = 'left'
        elif y_val > self.y_center + self.threshold: # 注意：ADC值越大通常对应摇杆向下拨动（或根据接线）
            current_direction = 'down' # 假设 Y 轴值越大是向下
        elif y_val < self.y_center - self.threshold:
            current_direction = 'up'   # 假设 Y 轴值越小是向上

        current_time = time.ticks_ms()
        if allow_repeat:
            if current_direction != 'center':
                # 如果允许重复，且当前方向不是中心，且距离上次同方向触发已超过延迟
                if current_direction != self._last_direction or \
                   time.ticks_diff(current_time, self._last_direction_time) > self.direction_repeat_delay_ms:
                    self._last_direction = current_direction
                    self._last_direction_time = current_time
                    return current_direction
                else: # 时间未到或方向未变（且不是center），则不重复触发
                    return 'center' # 或者返回 self._last_direction 如果希望持续输出
            else: # 如果是center
                self._last_direction = 'center'
                return 'center'
        else: # 不允许重复，只有方向改变时才返回
            if current_direction != self._last_direction:
                self._last_direction = current_direction
                return current_direction
            else:
                return 'center' # 方向未变，返回 'center' 表示无新方向事件

    def is_button_down(self):
        """
        检查按钮当前是否被按下（经过防抖处理）。
        Returns:
            bool: True 如果按钮被按下，False 如果按钮未被按下。
        """
        current_time = time.ticks_ms()
        raw_button_state = self.button.value() # 0 表示按下, 1 表示松开

        if raw_button_state != self._last_button_state:
            # 按钮状态发生变化，重置防抖计时器
            self._last_button_change_time = current_time
            self._last_button_state = raw_button_state

        # 只有当按钮状态稳定超过防抖时间才认为是有效状态
        if time.ticks_diff(current_time, self._last_button_change_time) > self.debounce_ms:
            return self._last_button_state == 0 # 按下为低电平
        else:
            # 仍在抖动期，返回上一个稳定状态的反值（因为当前值可能是抖动）
            # 或者更保守地，如果按钮当前是按下的，且在抖动期，也认为是按下的
            # 但为了避免误判，通常是等待抖动结束。
            # 这里简单处理：如果当前引脚读数是按下，就认为是按下，但外部调用需要注意频率。
            # 更精确的防抖是，只有稳定了一段时间才改变最终状态。
            # 为了简单，我们只在状态改变时重置计时器，然后判断是否超过抖动时间。
            # _last_button_state 已经是防抖后的状态了。
            return self._last_button_state == 0

    def is_button_clicked_once(self):
        """
        检测按钮是否被单击一次（按下后松开）。
        此函数被调用后会重置单击状态，确保每次单击只被检测到一次。
        需要在循环中频繁调用。
        """
        # 注意：这个实现比较简单，依赖于外部循环的调用时机。
        # 一个更鲁棒的实现可能需要在类内部管理更复杂的事件队列。
        pressed_now = self.is_button_down() # 获取防抖后的按钮状态

        if pressed_now and not self._button_was_pressed_for_click:
            # 按钮刚被按下
            self._button_was_pressed_for_click = True
            self._button_pressed_since_last_check = False # 重置
        elif not pressed_now and self._button_was_pressed_for_click:
            # 按钮刚被松开，且之前是按下状态，这构成一次单击
            self._button_was_pressed_for_click = False
            self._button_pressed_since_last_check = True # 标记为已单击
            return True # 返回 True 表示检测到单击

        # 如果调用时按钮已经松开，且之前标记过一次单击，则清除标记
        if not pressed_now and self._button_pressed_since_last_check:
            self._button_pressed_since_last_check = False
            # 注意：这里不返回 True，因为单击事件在松开的瞬间已经返回过了

        return False

    # --- 另一种更常用的单击检测方式 ---
    # 这个版本更容易在主循环中使用
    _button_state_for_click = 0 # 0: idle, 1: pressed, 2: released (click detected)
    _last_button_value_for_click = 1 # 初始为松开状态

    def check_for_single_click(self):
        """
        更推荐的单击检测方法。
        在主循环中调用此方法。如果返回 True，则发生了一次单击。
        """
        clicked = False
        current_value = self.button.value() # 直接读取引脚值
        current_time = time.ticks_ms()

        # 状态机处理按钮按下和松开
        if self._button_state_for_click == 0: # Idle state
            if current_value == 0 and self._last_button_value_for_click == 1: # 按钮从松开到按下
                # 状态改变，开始计时
                if time.ticks_diff(current_time, self._last_button_change_time) > self.debounce_ms:
                    self._button_state_for_click = 1 # 进入按下状态
                    self._button_down_start_time = current_time
                    self._last_button_change_time = current_time # 更新最后改变时间
        elif self._button_state_for_click == 1: # Pressed state
            if current_value == 1: # 按钮从按住到松开
                 if time.ticks_diff(current_time, self._last_button_change_time) > self.debounce_ms:
                    # 检查按下时长是否在单击阈值内 (可选，用于区分长按)
                    if time.ticks_diff(current_time, self._button_down_start_time) < self.click_threshold_ms:
                        clicked = True
                    self._button_state_for_click = 0 # 回到空闲状态
                    self._last_button_change_time = current_time
            elif current_value == 0: # 按钮仍然被按住
                # 如果需要长按事件，可以在这里检测按住时长
                pass


        self._last_button_value_for_click = current_value
        return clicked

    def calibrate(self, calibration_time_s=3):
        """
        一个简单的校准函数，用于自动获取摇杆中心值。
        在校准期间，用户不应触摸摇杆。
        Args:
            calibration_time_s (int): 校准持续时间（秒）。
        """
        print(f"摇杆校准开始，请勿触摸摇杆，持续 {calibration_time_s} 秒...")
        x_sum = 0
        y_sum = 0
        samples = 0
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < calibration_time_s * 1000:
            x_val, y_val = self.get_raw_values()
            x_sum += x_val
            y_sum += y_val
            samples += 1
            time.sleep_ms(10) # 短暂延迟

        if samples > 0:
            self.x_center = x_sum // samples
            self.y_center = y_sum // samples
            print(f"校准完成: X 中心 = {self.x_center}, Y 中心 = {self.y_center}")
        else:
            print("校准失败，没有采集到样本。")


# --- 如何在 main.py 中使用 (示例) ---
if __name__ == '__main__':
    # 假设引脚连接
    joystick = Joystick(x_pin_num=11, y_pin_num=12, button_pin_num=13)
    joystick.calibrate() # 可选，在程序启动时校准一次

    last_direction_print_time = 0
    direction_print_interval = 500 # 每500ms打印一次方向

    print("\n开始测试摇杆 (按 Ctrl+C 退出)...")
    print("移动摇杆或按下按钮:")

    while True:
        # 获取方向 (只在方向改变时获取，避免刷屏)
        direction = joystick.get_direction(allow_repeat=False) # 通常菜单操作用 allow_repeat=False
        if direction != 'center':
            print(f"摇杆方向: {direction.upper()}")

        # 或者，如果需要持续获取方向（例如游戏内移动）
        # direction_repeat = joystick.get_direction(allow_repeat=True)
        # current_ticks = time.ticks_ms()
        # if direction_repeat != 'center' and time.ticks_diff(current_ticks, last_direction_print_time) > direction_print_interval:
        #     print(f"摇杆方向 (持续): {direction_repeat.upper()}")
        #     last_direction_print_time = current_ticks


        # 检测单击事件 (推荐方式)
        if joystick.check_for_single_click():
            print("按钮被单击!")

        # 另一种方式：检测按钮是否按下 (持续)
        # if joystick.is_button_down():
        #     print("按钮当前被按下")
        # else:
        #     print("按钮当前已松开")

        # 读取原始值 (用于调试)
        # raw_x, raw_y = joystick.get_raw_values()
        # print(f"Raw X: {raw_x}, Raw Y: {raw_y}")

        time.sleep_ms(20) # 主循环延时，给其他操作留出时间，并控制摇杆读取频率
