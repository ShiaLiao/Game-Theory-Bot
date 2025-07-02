# game_trust_evolution.py
import random
# from collections import defaultdict # MicroPython 可能没有，用普通字典代替

# --- 游戏常量 ---
ACTIONS = ['C', 'D']  # C=信任，D=背叛
STATES = [(a, b) for a in ACTIONS for b in ACTIONS] # 所有可能的前一轮状态 (你的选择, 电脑的选择)

# 经典策略 (与原版相同)
classic_strategies = {
    '小天使': {s: 'C' for s in STATES},
    '老阴逼': {s: 'D' for s in STATES},
    '复读机': {('C', 'C'): 'C', ('C', 'D'): 'D', ('D', 'C'): 'C', ('D', 'D'): 'D'},
    '复仇者': {('C', 'C'): 'C', ('C', 'D'): 'D', ('D', 'C'): 'D', ('D', 'D'): 'D'},
    '混乱者': {s: random.choice(ACTIONS) for s in STATES},
}

# 游戏参数
TOTAL_ROUNDS = 10

class QLearningAgent:
    def __init__(self, actions, learning_rate=0.1, discount_factor=0.9, epsilon=0.1):
        # MicroPython 中 defaultdict 可能不可用，改用普通字典并检查键是否存在
        self.q_table = {} # 状态: [Q(C), Q(D)]
        self.actions = actions
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon

    def _get_q_values(self, state):
        """安全地获取 Q 值，如果状态不存在则初始化。"""
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0] # 初始化 Q(C) 和 Q(D)
        return self.q_table[state]

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.choice(self.actions)
        q_values = self._get_q_values(state)
        max_q = max(q_values)
        best_actions = [a for a, q in zip(self.actions, q_values) if q == max_q]
        return random.choice(best_actions)

    def learn(self, state, action, reward, next_state):
        action_idx = self.actions.index(action)
        q_predict_values = self._get_q_values(state) # 确保 state 被初始化
        q_predict = q_predict_values[action_idx]

        next_q_values = self._get_q_values(next_state) # 确保 next_state 被初始化
        q_target = reward + self.gamma * max(next_q_values)

        self.q_table[state][action_idx] += self.lr * (q_target - q_predict)

    def get_policy(self):
        policy = {}
        for state in STATES: # 遍历所有预定义状态
            q_values = self._get_q_values(state)
            max_q = max(q_values)
            best_actions = [a for a, q in zip(self.actions, q_values) if q == max_q]
            policy[state] = random.choice(best_actions)
        return policy

def analyze_policy(agent_policy):
    # (与原版相同)
    similarity = {}
    for name, policy in classic_strategies.items():
        match = sum(agent_policy.get(s, '') == policy[s] for s in STATES) # 使用 .get 避免 KeyError
        similarity[name] = match
    if not similarity: return "未知", {}
    best_match = max(similarity, key=similarity.get)
    return best_match, similarity

def calc_score(player, computer):
    # (与原版相同)
    if player == 'C' and computer == 'C': return 3, 3
    elif player == 'C' and computer == 'D': return 0, 5
    elif player == 'D' and computer == 'C': return 5, 0
    else: return 1, 1


class GameTrustEvolution:
    # 游戏内部状态定义
    STATE_INIT = 0          # 初始化和显示欢迎
    STATE_PLAYER_CHOICE = 1 # 等待玩家选择 (信任/背叛)
    STATE_CALCULATE = 2     # 计算结果并学习
    STATE_SHOW_ROUND_RESULT = 3 # 显示本轮结果
    STATE_GAME_OVER = 4     # 游戏结束，显示最终结果和分析

    def __init__(self, ui_manager, joystick):
        self.ui = ui_manager
        self.joystick = joystick
        self.agent = QLearningAgent(actions=ACTIONS)

        self.rounds_played = 0
        self.player_score = 0
        self.computer_score = 0
        # self.player_history = [] # 如果需要记录历史
        # self.computer_history = []

        # 初始状态设为 ('C', 'C')，表示上一轮双方都合作 (或游戏开始前)
        self.last_player_action = 'C'
        self.last_computer_action = 'C'

        self.current_game_state = self.STATE_INIT
        self.player_current_selection = 0 # 0 for 'C', 1 for 'D'
        self.options_menu = ["Trust (C)", "Evolution (D)"]

        # 用于存储本轮的电脑选择和玩家选择，以便在不同状态间传递
        self.this_round_comp_choice = None
        self.this_round_player_choice = None
        self.this_round_player_score_gain = 0
        self.this_round_computer_score_gain = 0


    def start_game(self):
        """由 main.py 调用，开始或重置游戏。"""
        self.rounds_played = 0
        self.player_score = 0
        self.computer_score = 0
        self.last_player_action = 'C'
        self.last_computer_action = 'C'
        self.agent = QLearningAgent(actions=ACTIONS) # 重置 AI 代理
        self.current_game_state = self.STATE_INIT
        self.player_current_selection = 0 # 默认选信任
        self.this_round_comp_choice = None
        self.this_round_player_choice = None
        # 初始化显示
        self._update_display()

    def _get_player_choice_from_joystick(self):
        """通过摇杆获取玩家选择。"""
        direction = self.joystick.get_direction(allow_repeat=False)
        clicked = self.joystick.check_for_single_click()

        if direction == 'up' or direction == 'left':
            self.player_current_selection = 0 # 信任
            self._update_display() # 更新菜单高亮
        elif direction == 'down' or direction == 'right':
            self.player_current_selection = 1 # 背叛
            self._update_display()

        if clicked:
            return ACTIONS[self.player_current_selection]
        return None # 没有确认选择

    def _update_display(self):
        """根据当前游戏状态更新 LED 显示。"""
        self.ui.clear_screen()
        title = f"ROUND {self.rounds_played + 1}/{TOTAL_ROUNDS} "
        info_lines = [
            f"Your points: {self.player_score}",
            f"Bot points: {self.computer_score}"
        ]

        if self.current_game_state == self.STATE_INIT:
            self.ui.show_message_box(
                ["Welcome to trust evolution!", "Ready?"],
                title="Game Start"
                # options=["开始"], # 可以加个开始按钮，但我们直接进入下一状态
            )
            # 实际上，INIT 状态应该由 main 管理，这里假设直接进入选择
            # self.current_game_state = self.STATE_PLAYER_CHOICE
            # self._update_display() # 立即刷新到选择界面

        elif self.current_game_state == self.STATE_PLAYER_CHOICE:
            # 使用 ui_manager 的菜单绘制功能
            self.ui.draw_menu(
                self.options_menu,
                self.player_current_selection,
                title=title,
                start_y=10 # 根据实际调整
            )
            # 在菜单下方显示分数
            y_offset = 10 + (len(self.options_menu) + 1) * (self.ui.char_height + self.ui.line_spacing * 2)
            for line in info_lines:
                self.ui.display_text_line(line, 5, y_offset, self.ui.text_color)
                y_offset += self.ui.char_height + self.ui.line_spacing

        elif self.current_game_state == self.STATE_SHOW_ROUND_RESULT:
            result_lines = [
                f"Your choice: {'trust' if self.this_round_player_choice == 'C' else 'evolution'}",
                f"Bot choice: {'trust' if self.this_round_comp_choice == 'C' else 'evolution'}",
                "---",
                f"Points for round:",
                f"  You: +{self.this_round_player_score_gain}",
                f"  Bot: +{self.this_round_computer_score_gain}",
                "---",
                "press to countinue..."
            ]
            self.ui.show_message_box(result_lines, title=title)

        elif self.current_game_state == self.STATE_GAME_OVER:
            final_lines = [
                f"Final points - You: {self.player_score}, Bot: {self.computer_score}"
            ]
            if self.player_score > self.computer_score: final_lines.append("Congratulation!")
            elif self.player_score < self.computer_score: final_lines.append("Unfortunately, the computer won!")
            else: final_lines.append("Draw!")

            agent_policy = self.agent.get_policy()
            best_match, _ = analyze_policy(agent_policy)
            final_lines.append(f"The current round of the computer strategy is close to: {best_match}")
            final_lines.append("---")
            final_lines.append("press to return to the main menu")
            self.ui.show_message_box(final_lines, title="Game over")

    def game_loop_tick(self):
        """
        游戏的主循环“tick”，由 main.py 在其循环中调用。
        返回:
            None: 游戏仍在进行中。
            str: 游戏结束时的结果消息 (或一个特定代码表示结束)。
        """
        if self.current_game_state == self.STATE_INIT:
            # 一般初始化完成后直接进入下一个状态
            self.current_game_state = self.STATE_PLAYER_CHOICE
            self._update_display()

        elif self.current_game_state == self.STATE_PLAYER_CHOICE:
            if self.rounds_played >= TOTAL_ROUNDS - 1: # 先检查是否已完成所有轮次
                self.current_game_state = self.STATE_GAME_OVER
                self._update_display()
                return None # 等待玩家在GAME_OVER状态按键

            player_action = self._get_player_choice_from_joystick()
            if player_action:
                self.this_round_player_choice = player_action
                # 电脑行动
                current_q_state = (self.last_player_action, self.last_computer_action)
                self.this_round_comp_choice = self.agent.choose_action(current_q_state)
                self.current_game_state = self.STATE_CALCULATE # 进入计算状态

        elif self.current_game_state == self.STATE_CALCULATE:
            ps, cs = calc_score(self.this_round_player_choice, self.this_round_comp_choice)
            self.player_score += ps
            self.computer_score += cs
            self.this_round_player_score_gain = ps
            self.this_round_computer_score_gain = cs

            # Q-Learning 学习
            prev_q_state = (self.last_player_action, self.last_computer_action)
            next_q_state = (self.this_round_player_choice, self.this_round_comp_choice)
            self.agent.learn(prev_q_state, self.this_round_comp_choice, cs, next_q_state)

            # 更新上一轮的行动
            self.last_player_action = self.this_round_player_choice
            self.last_computer_action = self.this_round_comp_choice

            self.rounds_played += 1
            self.current_game_state = self.STATE_SHOW_ROUND_RESULT
            self._update_display()

        elif self.current_game_state == self.STATE_SHOW_ROUND_RESULT:
            if self.joystick.check_for_single_click(): # 等待玩家按键继续
                if self.rounds_played >= TOTAL_ROUNDS - 1:
                    self.current_game_state = self.STATE_GAME_OVER
                else:
                    self.current_game_state = self.STATE_PLAYER_CHOICE # 开始下一轮选择
                self._update_display()

        elif self.current_game_state == self.STATE_GAME_OVER:
            if self.joystick.check_for_single_click(): # 等待玩家按键返回主菜单
                return "GAME_ENDED_TE" # 返回一个特殊标记给 main.py

        return None # 游戏仍在进行
