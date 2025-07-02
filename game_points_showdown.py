import random
import time
from machine import Pin, ADC

class GamePointsShowdown:
    # 游戏内部状态定义
    STATE_INIT = 0          # 初始化和显示欢迎
    STATE_PLAYER_BET = 1     # 玩家下注阶段
    STATE_MACHINE_BET = 2    # 机器下注阶段
    STATE_SHOW_RESULT = 3    # 显示本轮结果
    STATE_GAME_OVER = 4      # 游戏结束
    
    def __init__(self, ui_manager, joystick):
        self.ui = ui_manager
        self.joystick = joystick
        self.current_game_state = self.STATE_INIT
        
        # 游戏参数
        self.TOTAL_ROUNDS = 5
        self.INITIAL_POINTS = 50
        
        # 玩家和机器状态
        self.player_points = self.INITIAL_POINTS
        self.machine = QLearningAgent(self.INITIAL_POINTS)
        self.player_score = 0
        self.machine_score = 0
        self.current_round = 0
        self.player_last_bet = 3  # 初始假设
        
        # 当前轮次数据
        self.player_bet = 0
        self.machine_bet = 0
        self.round_result = ""
        
        # 下注选择相关
        self.current_bet_selection = 0
        self.max_bet = self.INITIAL_POINTS
        
    def start_game(self):
        """由 main.py 调用，开始或重置游戏"""
        self.current_game_state = self.STATE_INIT
        self.player_points = self.INITIAL_POINTS
        self.machine = QLearningAgent(self.INITIAL_POINTS)
        self.player_score = 0
        self.machine_score = 0
        self.current_round = 0
        self.player_last_bet = 3
        self._update_display()
        
    def _update_display(self):
        """根据当前游戏状态更新显示"""
        self.ui.clear_screen()
        
        title = f"Points Showdown - Round {self.current_round + 1}/{self.TOTAL_ROUNDS}"
        info_lines = [
            f"Your points: {self.player_points}",
            f"Machine points: {self.machine.remaining_points}",
            f"Score: You {self.player_score}-{self.machine_score} Machine"
        ]
        
        if self.current_game_state == self.STATE_INIT:
            self.ui.show_message_box(
                ["Welcome to Points Showdown!", 
                 f"Each starts with {self.INITIAL_POINTS} points",
                 "Higher bet wins the round",
                 "Press button to start"],
                title="Game Start"
            )
            
        elif self.current_game_state == self.STATE_PLAYER_BET:
            # 显示下注界面
            self.ui.draw_menu(
                [f"Bet: {self.current_bet_selection}"],
                0,
                title=title,
                start_y=10
            )
            
            # 显示说明和当前状态
            y_offset = 10 + (1 + 1) * (self.ui.char_height + self.ui.line_spacing * 2)
            for line in info_lines:
                self.ui.display_text_line(line, 5, y_offset, self.ui.text_color)
                y_offset += self.ui.char_height + self.ui.line_spacing
                
            # 下注说明
            help_lines = [
                "Up/Down:+-1",
                "Left/Right:+-5",
                "Press to confirm"
                ]
            line_height = 10  # 调整行高，取决于你的字体大小
            current_y = y_offset
            for line in help_lines:
                self.ui.display_text_line(line, 5, current_y, self.ui.text_color)
                current_y += line_height  # 每次增加行高，使下一行显示在下方
            
        elif self.current_game_state == self.STATE_MACHINE_BET:
            # 显示机器下注
            result_lines = [
                f"Your bet: {self.player_bet}",
                f"Machine bet: {self.machine_bet}",
                "---",
                self.round_result,
                "---",
                "Press to continue..."
            ]
            self.ui.show_message_box(result_lines, title=title)
            
        elif self.current_game_state == self.STATE_SHOW_RESULT:
            # 显示完整回合结果
            result_lines = [
                f"Round {self.current_round} result:",
                f"Your bet: {self.player_bet}",
                f"Machine bet: {self.machine_bet}",
                "---",
                self.round_result,
                f"Score: You {self.player_score}-{self.machine_score} Machine",
                "---",
                "Press to continue..."
            ]
            self.ui.show_message_box(result_lines, title="Round Over")
            
        elif self.current_game_state == self.STATE_GAME_OVER:
            # 游戏结束显示
            final_lines = [
                "Game Over!",
                f"Final Score: You {self.player_score}-{self.machine_score} Machine",
                "---"
            ]
            
            if self.player_score > self.machine_score:
                final_lines.append("You win!")
            elif self.player_score < self.machine_score:
                final_lines.append("Machine wins!")
            else:
                final_lines.append("It's a tie!")
                
            final_lines.append("Press to return to menu")
            self.ui.show_message_box(final_lines, title="Game Over")
    
    def _handle_player_bet_input(self):
        """处理玩家下注输入"""
        direction = self.joystick.get_direction(allow_repeat=False)
        clicked = self.joystick.check_for_single_click()
        
        if direction == 'up':
            self.current_bet_selection = min(self.current_bet_selection + 1, self.max_bet)
            self._update_display()
        elif direction == 'down':
            self.current_bet_selection = max(self.current_bet_selection - 1, 0)
            self._update_display()
        elif direction == 'right':
            self.current_bet_selection = min(self.current_bet_selection + 5, self.max_bet)
            self._update_display()
        elif direction == 'left':
            self.current_bet_selection = max(self.current_bet_selection - 5, 0)
            self._update_display()
            
        if clicked:
            self.player_bet = self.current_bet_selection
            self.player_points -= self.player_bet
            return True
            
        return False
    
    def game_loop_tick(self):
        """游戏的主循环tick，由main.py调用"""
        if self.current_game_state == self.STATE_INIT:
            if self.joystick.check_for_single_click():
                self.current_game_state = self.STATE_PLAYER_BET
                self.max_bet = self.player_points
                self.current_bet_selection = min(5, self.max_bet)
                self._update_display()
                
        elif self.current_game_state == self.STATE_PLAYER_BET:
            if self._handle_player_bet_input():
                # 玩家确认下注，机器下注
                self.machine_bet = self.machine.make_decision(self.player_points, self.player_last_bet)
                self.machine.remaining_points -= self.machine_bet
                
                # 判断胜负
                if self.player_bet > self.machine_bet:
                    self.player_score += 1
                    reward = -1  # 机器输
                    self.round_result = "You win this round!"
                elif self.machine_bet > self.player_bet:
                    self.machine_score += 1
                    reward = 1   # 机器赢
                    self.round_result = "Machine wins this round!"
                else:
                    reward = 0
                    self.round_result = "It's a tie!"
                
                # 更新Q表
                self.machine.update_q_table(reward, self.player_points, self.player_bet)
                self.player_last_bet = self.player_bet
                
                self.current_round += 1
                self.current_game_state = self.STATE_MACHINE_BET
                self._update_display()
                
        elif self.current_game_state == self.STATE_MACHINE_BET:
            if self.joystick.check_for_single_click():
                if self.current_round >= self.TOTAL_ROUNDS:
                    self.current_game_state = self.STATE_GAME_OVER
                else:
                    self.current_game_state = self.STATE_SHOW_RESULT
                self._update_display()
                
        elif self.current_game_state == self.STATE_SHOW_RESULT:
            if self.joystick.check_for_single_click():
                self.current_game_state = self.STATE_PLAYER_BET
                self.max_bet = self.player_points
                self.current_bet_selection = min(5, self.max_bet)
                self._update_display()
                
        elif self.current_game_state == self.STATE_GAME_OVER:
            if self.joystick.check_for_single_click():
                return "GAME_ENDED_PS"  # 返回结束信号给主程序
                
        return None  # 游戏仍在进行


class QLearningAgent:
    def __init__(self, total_points):
        # 初始化Q表（用普通字典替代defaultdict）
        self.q_table = {}  # 格式: {state: [action_values]}
        self.total_points = total_points
        self.remaining_points = total_points  # 机器当前剩余积分
        self.alpha = 0.1    # 学习率
        self.gamma = 0.9    # 折扣因子
        self.epsilon = 0.3  # 探索概率
        self.last_state = None  # 上轮状态
        self.last_action = None # 上轮动作
        self.round = 0       # 当前轮次

    def get_state_key(self, user_remaining, user_last_bet):
        """生成状态键（不使用对象等不可哈希类型）"""
        return (
            5 - self.round,  # 剩余轮次
            self.remaining_points // 5, # 机器积分分组（每5分一组）
            user_remaining // 5,        # 玩家积分分组
            min(user_last_bet, 25)      # 玩家上轮下注（上限25）
        )

    def init_state_if_new(self, state_key):
        """如果状态不存在则初始化Q值数组"""
        if state_key not in self.q_table:
            # 初始化动作值数组（长度为总积分+1）
            self.q_table[state_key] = [
                random.random() * 0.1  # 小随机数打破对称性
                for _ in range(self.total_points + 1)
            ]

    def choose_action(self, state_key):
        """ε-greedy策略选择动作"""
        valid_actions = range(1, min(self.remaining_points, 25) + 1)
        # 探索：随机选择合法动作
        if random.random() < self.epsilon:
            return random.choice(valid_actions)
        # 利用：选择Q值最高的动作
        q_values = self.q_table[state_key]
        max_q = -float('inf')
        best_action = 1
        for a in valid_actions:
            if q_values[a] > max_q:
                max_q = q_values[a]
                best_action = a
        return best_action

    def make_decision(self, user_remaining, user_last_bet):
        """生成机器下注决策"""
        self.round += 1
        state_key = self.get_state_key(user_remaining, user_last_bet)
        self.init_state_if_new(state_key)  # 确保状态已初始化
        
        # 终局策略：最后一轮全力下注
        if 5 - self.round == 0 and self.remaining_points > 1:
            return self.remaining_points
            
        action = self.choose_action(state_key)
        
        # 非终局保留至少1分/剩余轮次
        remaining_rounds = 5 - self.round
        reserve = max(0, remaining_rounds - 1)
        action = min(action, self.remaining_points - reserve)
        
        self.last_state = state_key
        self.last_action = action
        return max(1, action)  # 至少下注1分

    def update_q_table(self, reward, new_user_remaining, new_user_bet):
        """Q-learning更新"""
        if self.last_state is None:
            return
            
        new_state_key = self.get_state_key(new_user_remaining, new_user_bet)
        self.init_state_if_new(new_state_key)
        
        # Q值更新公式
        old_value = self.q_table[self.last_state][self.last_action]
        next_max = max(self.q_table[new_state_key])
        new_value = old_value + self.alpha * (
            reward + self.gamma * next_max - old_value
        )
        self.q_table[self.last_state][self.last_action] = new_value
        
        # 衰减探索率
        self.epsilon *= 0.95
