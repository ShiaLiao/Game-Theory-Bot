# main.py
import time
from machine import Pin, SPI # MicroPython 的 GPIO 和 SPI 控制

# --- 占位符：导入驱动和游戏模块 ---
# 请确保这些文件名与你实际保存的文件名一致
try:
    from display_driver import ST7789
    from ui_manager import UIManager
    from joystick_driver import Joystick
    from game_trust_evolution import GameTrustEvolution
    from game_points_showdown import GamePointsShowdown
    from game_auction import AuctionGame
except ImportError as e:
    print(f"!!! 关键模块导入失败: {e} !!!")
    print("请检查模块文件是否存在于 ESP32 上，并且文件名正确。")
    # 在这里可以尝试在屏幕上显示错误，如果屏幕驱动能早期加载的话
    # 或者让板载LED闪烁等方式提示错误
    raise # 抛出异常，停止程序，因为没有这些模块无法运行

# --- 全局状态定义 ---
STATE_INIT_HW = -1            # 硬件初始化状态
STATE_WELCOME_SCREEN = 0      # 显示欢迎界面
STATE_MAIN_MENU = 1           # 主菜单
STATE_GAME_TE_INIT = 10       # 信任与进化 - 初始化
STATE_GAME_TE_RUNNING = 11    # 信任与进化 - 运行中
STATE_GAME_PS_INIT = 20       # 点数对决 - 初始化
STATE_GAME_PS_RUNNING = 21    # 点数对决 - 运行中
STATE_GAME_AUCTION_INIT = 30  # 拍卖游戏 - 初始化
STATE_GAME_AUCTION_RUNNING = 31 # 拍卖游戏 - 运行中
STATE_EXITING = 99            # 退出程序状态

current_state = STATE_INIT_HW # 初始状态为硬件初始化
running = True

# --- 硬件和驱动实例 (全局变量，在 initialize_hardware 中赋值) ---
spi_bus = None
st7789_dev = None
ui = None # UIManager 实例
joystick_dev = None # Joystick 实例

# --- 游戏实例 (全局变量) ---
game_te_instance = None
game_ps_instance = None
game_auction_instance = None

# --- 主菜单定义 ---
main_menu_items = [
    "1. game_trust_evolution",
    "2. game_points_showdown",
    "3. game_auction",
    "4. exit"
]
main_menu_selected_idx = 0

# --- 硬件配置占位符 (根据实际接线填写) ---
# SPI 总线配置
SPI_BUS_ID = 1  # 通常是 1 (VSPI) 或 2 (HSPI)
SPI_BAUDRATE = 40000000 # 40 MHz
SPI_SCK_PIN_NUM = 12    # 占位符
SPI_MOSI_PIN_NUM = 11   # 占位符
# SPI_MISO_PIN_NUM = 19 # 如果屏幕或SPI设备需要MISO

# ST7789 屏幕控制引脚
ST7789_DC_PIN_NUM = 2    # 占位符
ST7789_RST_PIN_NUM = 5   # 占位符
ST7789_BL_PIN_NUM = 13
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 320
SCREEN_ROTATION = 0 # 0, 1, 2, or 3

# Joystick 引脚配置
JOYSTICK_X_PIN_NUM = 16     # 占位符 (来自崔的代码)
JOYSTICK_Y_PIN_NUM = 17     # 占位符 (来自崔的代码)
JOYSTICK_BTN_PIN_NUM = 18   # 占位符 (来自崔的代码)
# Joystick 校准参数 (可以由 calibrate() 自动获取，或在此处预设)
JOYSTICK_X_CENTER = 2048 # 占位符
JOYSTICK_Y_CENTER = 2048 # 占位符
JOYSTICK_THRESHOLD = 800 # 占位符

# --- 初始化函数 ---
def initialize_hardware():
    global spi_bus, st7789_dev, ui, joystick_dev
    print("正在初始化硬件...")
    try:
        # 1. 初始化 SPI 总线
        sck_pin = Pin(SPI_SCK_PIN_NUM)
        mosi_pin = Pin(SPI_MOSI_PIN_NUM)
        # miso_pin = Pin(SPI_MISO_PIN_NUM) # 如果需要
        spi_bus = SPI(SPI_BUS_ID, baudrate=SPI_BAUDRATE,polarity=1,phase=1,sck=sck_pin, mosi=mosi_pin) # miso=miso_pin
        print("- SPI 总线初始化完成。")

        # 2. 初始化 ST7789 屏幕驱动
        dc_pin = Pin(ST7789_DC_PIN_NUM, Pin.OUT)
        rst_pin = Pin(ST7789_RST_PIN_NUM, Pin.OUT)
        bl_pin = None
        if ST7789_BL_PIN_NUM is not None:
            bl_pin = Pin(ST7789_BL_PIN_NUM, Pin.OUT)

        st7789_dev = ST7789(
            spi_bus,
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            dc=dc_pin,
            cs=None,
            reset=rst_pin,
            backlight=bl_pin,
            rotation=SCREEN_ROTATION
        )
        print("- ST7789 屏幕驱动初始化完成。")
        if bl_pin:
            st7789_dev.backlight(1) # 打开背光

        # 3. 初始化 UI 管理器
        ui = UIManager(st7789_dev) # 假设 UIManager 构造函数只需要屏幕驱动实例
        print("- UI 管理器初始化完成。")

        # 4. 初始化摇杆驱动
        joystick_dev = Joystick(
            JOYSTICK_X_PIN_NUM,
            JOYSTICK_Y_PIN_NUM,
            JOYSTICK_BTN_PIN_NUM,
            x_center=JOYSTICK_X_CENTER, # 可以传入预设值
            y_center=JOYSTICK_Y_CENTER,
            threshold=JOYSTICK_THRESHOLD
        )
        # ui.show_message_box(["准备校准摇杆", "请勿触摸", "按键开始"], title="校准提示")
        # while not joystick_dev.check_for_single_click(): time.sleep_ms(20) # 等待按键开始校准
        # ui.clear_screen()
        # ui.display_text_line("校准中...", 10, SCREEN_HEIGHT // 2, ui.text_color)
        joystick_dev.calibrate(calibration_time_s=2) # 运行摇杆校准
        print("- 摇杆驱动初始化并校准完成。")

        print("硬件初始化成功！")
        return True
    except Exception as e:
        print(f"!!! 硬件初始化失败: {e} !!!")
        # 尝试在屏幕上显示错误（如果屏幕部分初始化成功）
        if st7789_dev: # 即使UI管理器没成功，底层驱动可能可以画点东西
            try:
                st7789_dev.fill(st7789_dev.RED) # 用红色填充屏幕表示错误
                # 尝试用framebuf显示简单文本，如果UIManager失败了
                # from framebuf import FrameBuffer, MONO_HLSB
                # buf = bytearray(8 * (len(str(e)) // 8 +1)) # 粗略计算
                # fbuf = FrameBuffer(buf, len(str(e))*8, 8, MONO_HLSB)
                # fbuf.text(str(e),0,0,1)
                # # 还需要将fbuf绘制到屏幕
            except:
                pass # 如果连屏幕都画不了，就没办法了
        return False

# --- 主菜单处理函数 ---
def handle_main_menu_input():
    global main_menu_selected_idx, current_state, running
    global game_te_instance, game_ps_instance, game_auction_instance

    direction = joystick_dev.get_direction(allow_repeat=False)
    clicked = joystick_dev.check_for_single_click()

    if direction == 'up':
        main_menu_selected_idx = (main_menu_selected_idx - 1 + len(main_menu_items)) % len(main_menu_items)
        ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
    elif direction == 'down':
        main_menu_selected_idx = (main_menu_selected_idx + 1) % len(main_menu_items)
        ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
    elif clicked:
        selected_option = main_menu_items[main_menu_selected_idx]
        if selected_option == "1. game_trust_evolution":
            current_state = STATE_GAME_TE_INIT
        elif selected_option == "2. game_points_showdown":
            current_state = STATE_GAME_PS_INIT
        elif selected_option == "3. game_auction":
            current_state = STATE_GAME_AUCTION_INIT
        elif selected_option == "4. exit":
            current_state = STATE_EXITING
        # 清理可能存在的旧游戏实例 (或者在游戏结束时清理)
        game_te_instance = None
        game_ps_instance = None
        game_auction_instance = None

# --- 主循环 ---
def main_loop():
    global current_state, running
    global game_te_instance, game_ps_instance, game_auction_instance, main_menu_selected_idx

    while running:
        # --- 根据当前状态执行操作 ---
        if current_state == STATE_INIT_HW:
            if initialize_hardware():
                current_state = STATE_WELCOME_SCREEN
                ui.show_welcome_screen() # 显示欢迎界面
                # 等待片刻或按键继续
                start_time = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start_time) < 2000: # 显示2秒
                    if joystick_dev.check_for_single_click(): break # 按键可跳过
                    time.sleep_ms(20)
                current_state = STATE_MAIN_MENU
                ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
            else:
                running = False # 硬件初始化失败，无法继续

        elif current_state == STATE_WELCOME_SCREEN:
             # 在 initialize_hardware 后已经处理，这里可以留空或用于其他逻辑
             pass


        elif current_state == STATE_MAIN_MENU:
            handle_main_menu_input()

        # --- 信任与进化 ---
        elif current_state == STATE_GAME_TE_INIT:
            if game_te_instance is None:
                game_te_instance = GameTrustEvolution(ui, joystick_dev)
            game_te_instance.start_game()
            current_state = STATE_GAME_TE_RUNNING
        elif current_state == STATE_GAME_TE_RUNNING:
            if game_te_instance:
                game_status = game_te_instance.game_loop_tick()
                if game_status == "GAME_ENDED_TE":
                    current_state = STATE_MAIN_MENU
                    ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
                    game_te_instance = None # 清理实例

        # --- 点数对决 ---
        elif current_state == STATE_GAME_PS_INIT:
            if game_ps_instance is None:
                game_ps_instance = GamePointsShowdown(ui, joystick_dev)
            game_ps_instance.start_game()
            current_state = STATE_GAME_PS_RUNNING
        elif current_state == STATE_GAME_PS_RUNNING:
            if game_ps_instance:
                game_status = game_ps_instance.game_loop_tick()
                if game_status == "GAME_ENDED_PS":
                    current_state = STATE_MAIN_MENU
                    ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
                    game_ps_instance = None

        # --- 拍卖游戏 ---
        elif current_state == STATE_GAME_AUCTION_INIT:
            if game_auction_instance is None:
                game_auction_instance = AuctionGame(ui, joystick_dev)
            game_auction_instance.start_game()
            current_state = STATE_GAME_AUCTION_RUNNING
        elif current_state == STATE_GAME_AUCTION_RUNNING:
            if game_auction_instance:
                game_status = game_auction_instance.game_loop_tick()
                if game_status == "GAME_ENDED_AUCTION":
                    current_state = STATE_MAIN_MENU
                    ui.draw_menu(main_menu_items, main_menu_selected_idx, title="gambling bot")
                    game_auction_instance = None

        elif current_state == STATE_EXITING:
            running = False # 触发循环结束
            if ui: # 确保ui已初始化
                ui.clear_screen()
                ui.show_message_box(["Thank you!", "Turning off the bot..."], title="Good bye")
            print("机器人正在关闭...")
            time.sleep(2) # 给用户时间看屏幕

        # 主循环延时，控制帧率，避免CPU满载
        time.sleep_ms(30) # 约 33 FPS，可以根据需要调整

# --- 程序入口 ---
if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("程序被用户中断。")
        running = False # 确保循环会退出
    except Exception as e:
        print(f"!!! 主程序发生未捕获的严重错误: {e} !!!")
        running = False
        # 尝试在屏幕上显示最终错误
        if ui:
            try:
                ui.show_error_message(f"主程序错误: {str(e)[:100]}") # 显示部分错误信息
            except:
                print("UI管理器也无法显示错误。")
        elif st7789_dev: # 如果只有底层驱动
             try:
                st7789_dev.fill(st7789_dev.RED)
             except:
                pass
    finally:
        print("清理程序...")
        if st7789_dev and ST7789_BL_PIN_NUM is not None:
            try:
                st7789_dev.backlight(0) # 关闭背光
                st7789_dev.fill(st7789_dev.BLACK) # 清屏
            except:
                pass
        print("程序已退出。")
