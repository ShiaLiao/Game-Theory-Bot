import random
import time
from machine import Pin, ADC
import urandom

def shuffle(lst):
    """Fisher-Yates shuffle算法"""
    for i in range(len(lst)-1, 0, -1):
        j = urandom.getrandbits(8) % (i + 1)
        lst[i], lst[j] = lst[j], lst[i]

class AuctionGame:
    # Game state definitions
    STATE_INIT = 0            # Initialization and welcome screen
    STATE_PLAYER_SELECT = 1   # Player selecting item to auction
    STATE_ITEM_CONFIRM = 2    # Confirm item selection
    STATE_AUCTION = 3         # Auction in progress
    STATE_BID_CONFIRM = 4     # Confirm bid amount
    STATE_ROUND_RESULT = 5    # Showing round results
    STATE_GAME_OVER = 6       # Game over screen
    
    # Item definitions (name, actual value, estimated range)
    ITEMS = [
        ("Apple", 8, (5, 10)),
        ("Banana", 6, (4, 8)),
        ("Orange", 7, (5, 9)),
        ("Grape", 10, (8, 12)),
        ("Melon", 15, (12, 18)),
        ("Pineapple", 12, (10, 14)),
        ("Strawberry", 9, (7, 11)),
        ("Blueberry", 11, (9, 13))
    ]
    
    def __init__(self, ui_manager, joystick):
        self.ui = ui_manager
        self.joystick = joystick
        self.current_game_state = self.STATE_INIT
        
        # Game parameters
        self.INITIAL_CASH = 100
        self.ITEMS_PER_PLAYER = 2
        self.TOTAL_ROUNDS = 2
        
        # Players
        self.players = [
            {"name": "Player", "cash": self.INITIAL_CASH, "items": [], "is_ai": False},
            {"name": "AI 1", "cash": self.INITIAL_CASH, "items": [], "is_ai": True},
            {"name": "AI 2", "cash": self.INITIAL_CASH, "items": [], "is_ai": True}
        ]
        
        # Game state
        self.current_round = 0
        self.current_player_idx = 0
        self.current_bidder_idx = 0
        self.selected_item_idx = 0
        self.auction_item = None
        self.current_bid = 0
        self.highest_bidder = None
        self.message = ""
        self.passes = 0
        self.waiting_for_confirm = False  # 新增：用于确认状态
    
    def start_game(self):
        """Called by main.py to start/reset the game"""
        self.current_game_state = self.STATE_INIT
        self._reset_game()
        self._update_display()
        
    def _reset_game(self):
        """Reset all game state"""
        # Reset players
        for p in self.players:
            p["cash"] = self.INITIAL_CASH
            p["items"] = []
        
        # Distribute items
        available_items = self.ITEMS.copy()
        shuffle(available_items)
        
        for p in self.players:
            for _ in range(self.ITEMS_PER_PLAYER):
                if available_items:
                    p["items"].append(available_items.pop())
        
        # Balance total assets
        assets = [self._total_assets(p) for p in self.players]
        avg_assets = sum(assets) // len(assets)
        for p in self.players:
            p["cash"] += (avg_assets - self._total_assets(p))
        
        # Reset game state
        self.current_round = 0
        self.current_player_idx = 0
        self.current_bidder_idx = 0
        self.selected_item_idx = 0
        self.auction_item = None
        self.current_bid = 0
        self.highest_bidder = None
        self.message = ""
        self.passes = 0
        self.waiting_for_confirm = False
    
    def _total_assets(self, player):
        """Calculate player's total assets"""
        return player["cash"] + sum(item[1] for item in player["items"])
    
    def _update_display(self):
        """Update display based on current game state"""
        self.ui.clear_screen()
        
        if self.current_game_state == self.STATE_INIT:
            self.ui.show_message_box(
                ["Auction Game", 
                 f"Start with ${self.INITIAL_CASH}",
                 f"& {self.ITEMS_PER_PLAYER} items",
                 "Press to start"],
                title="Welcome"
            )
            
        elif self.current_game_state == self.STATE_PLAYER_SELECT:
            player = self.players[self.current_player_idx]
            title = f"Round {self.current_round+1}/{self.TOTAL_ROUNDS}"
            
            # Show player status
            status = [
                f"{player['name']}'s turn",
                f"Cash: ${player['cash']}",
                "Items:"
            ]
            
            # Show items with selection
            items_display = []
            for i, item in enumerate(player["items"]):
                selected = ">" if i == self.selected_item_idx else " "
                items_display.append(f"{selected}{item[0]} (${item[1]})")
            
            # Combine all lines
            lines = status + items_display + ["", "Up/Down: Select", "Press: Choose"]
            self.ui.show_message_box(lines, title=title)
            
        elif self.current_game_state == self.STATE_ITEM_CONFIRM:
            player = self.players[self.current_player_idx]
            item = player["items"][self.selected_item_idx]
            lines = [
                f"Confirm auction item:",
                f"{item[0]} (Value: ${item[1]})",
                f"Estimate: ${item[2][0]}-{item[2][1]}",
                "",
                "Press: Confirm",
                "Left/Right: Cancel"
            ]
            self.ui.show_message_box(lines, title="Confirm Item")
            
        elif self.current_game_state == self.STATE_AUCTION:
            title = f"Auction: {self.auction_item[0]}"
            seller = self.players[self.current_player_idx]
            bidder = self.players[self.current_bidder_idx]
            
            # Safely handle highest_bidder being None
            high_bidder_name = "None"
            if self.highest_bidder is not None and 0 <= self.highest_bidder < len(self.players):
                high_bidder_name = self.players[self.highest_bidder]['name']
            
            lines = [
                f"Seller: {seller['name']}",
                f"Bidder: {bidder['name']}",
                "",
                f"Value: ${self.auction_item[1]}",
                f"Estimate: ${self.auction_item[2][0]}-{self.auction_item[2][1]}",
                "",
                f"Current bid: ${self.current_bid}",
                f"High bidder: {high_bidder_name}"
            ]
            
            if bidder["is_ai"]:
                lines.append("")
                lines.append("AI thinking...")
            else:
                lines.append("")
                lines.append("Up: +1  Down: -1")
                lines.append("Left: +5 Right: -5")
                lines.append("Press: Confirm Bid")
            
            self.ui.show_message_box(lines, title=title)
            
        elif self.current_game_state == self.STATE_BID_CONFIRM:
            bidder = self.players[self.current_bidder_idx]
            lines = [
                f"Confirm your bid:",
                f"Amount: ${self.current_bid}",
                f"Your cash: ${bidder['cash']}",
                "",
                "Press: Confirm",
                "Left/Right: Cancel"
            ]
            self.ui.show_message_box(lines, title="Confirm Bid")
            
        elif self.current_game_state == self.STATE_ROUND_RESULT:
            title = "Round Result"
            lines = [
                f"Item: {self.auction_item[0]}",
                f"Winner: {self.players[self.highest_bidder]['name'] if self.highest_bidder is not None else 'No winner'}",
                f"Price: ${self.current_bid}",
                "",
                "Player assets:"
            ]
            
            for p in self.players:
                lines.append(f"{p['name']}: ${self._total_assets(p)}")
            
            lines.append("")
            lines.append("Press to continue")
            
            self.ui.show_message_box(lines, title=title)
            
        elif self.current_game_state == self.STATE_GAME_OVER:
            title = "Game Over"
            
            # Sort players by total assets
            ranked = sorted(
                [(p['name'], self._total_assets(p)) for p in self.players],
                key=lambda x: x[1],
                reverse=True
            )
            
            lines = ["Final Scores:"]
            for i, (name, assets) in enumerate(ranked):
                lines.append(f"{i+1}. {name}: ${assets}")
            
            lines.append("")
            lines.append("Press to exit")
            
            self.ui.show_message_box(lines, title=title)
    
    
    def _ai_bid(self, player_idx):
        """AI bidding logic"""
        player = self.players[player_idx]
        item = self.auction_item
        
        if not player["cash"] > self.current_bid:
            return self.current_bid  # Can't bid higher
            
        # Calculate estimated value
        est_min, est_max = item[2]
        est_value = (est_min + est_max) // 2
        
        # Calculate max bid (120% of estimated value)
        max_bid = min(int(est_value * 1.2), player["cash"])
        
        # Random decision to bid
        if random.random() < 0.7:  # 70% chance to bid
            bid_increase = random.randint(1, 5)
            new_bid = self.current_bid + bid_increase
            return min(new_bid, max_bid)
        
        return self.current_bid
    
    def _next_player(self):
        """Move to next player's turn"""
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        
        # If we've gone full circle, advance round
        if self.current_player_idx == 0:
            self.current_round += 1
            
            # Check if game is over
            if self.current_round >= self.TOTAL_ROUNDS:
                self.current_game_state = self.STATE_GAME_OVER
            else:
                self.message = f"Round {self.current_round+1} started"
    
    def game_loop_tick(self):
        """Main game loop tick called by main.py"""
        if self.current_game_state == self.STATE_INIT:
            if self.joystick.check_for_single_click():
                self.current_game_state = self.STATE_PLAYER_SELECT
                self._update_display()
                
        elif self.current_game_state == self.STATE_PLAYER_SELECT:
            # Handle item selection
            direction = self.joystick.get_direction(allow_repeat=False)
            clicked = self.joystick.check_for_single_click()
            
            player = self.players[self.current_player_idx]
            item_count = len(player["items"])
            
            if direction == 'up':
                self.selected_item_idx = (self.selected_item_idx - 1) % item_count
                self._update_display()
            elif direction == 'down':
                self.selected_item_idx = (self.selected_item_idx + 1) % item_count
                self._update_display()
            elif clicked and item_count > 0:
                # 进入物品确认状态
                self.current_game_state = self.STATE_ITEM_CONFIRM
                self._update_display()
            elif clicked and item_count == 0:
                # Player has no items, skip turn
                self._next_player()
                self._update_display()
                
        elif self.current_game_state == self.STATE_ITEM_CONFIRM:
            # 确认或取消选择物品
            clicked = self.joystick.check_for_single_click()
            direction = self.joystick.get_direction(allow_repeat=False)
            
            if clicked:
                # 确认选择，开始拍卖
                player = self.players[self.current_player_idx]
                self.auction_item = player["items"].pop(self.selected_item_idx)
                self.current_bid = 0
                self.highest_bidder = None
                self.passes = 0
                self.current_bidder_idx = (self.current_player_idx + 1) % len(self.players)
                self.current_game_state = self.STATE_AUCTION
                self._update_display()
            elif direction in ('left', 'right'):
                # 取消选择，返回物品选择
                self.current_game_state = self.STATE_PLAYER_SELECT
                self._update_display()
                
        elif self.current_game_state == self.STATE_AUCTION:
            player = self.players[self.current_bidder_idx]
            
            if player["is_ai"]:
                # AI turn - make bid decision
                time.sleep(0.5)  # Simulate thinking
                new_bid = self._ai_bid(self.current_bidder_idx)
                
                if new_bid > self.current_bid:
                    self.current_bid = new_bid
                    self.highest_bidder = self.current_bidder_idx
                    self.passes = 0
                else:
                    self.passes += 1
                
                # Move to next bidder
                self.current_bidder_idx = (self.current_bidder_idx + 1) % len(self.players)
                self._update_display()
            else:
                # Human player turn
                direction = self.joystick.get_direction(allow_repeat=False)
                clicked = self.joystick.check_for_single_click()
                
                if direction == 'up':
                    self.current_bid = min(self.current_bid + 1, player["cash"])
                    self._update_display()
                elif direction == 'down':
                    self.current_bid = max(self.current_bid - 1, 0)
                    self._update_display()
                elif direction == 'right':
                    self.current_bid = min(self.current_bid + 5, player["cash"])
                    self._update_display()
                elif direction == 'left':
                    self.current_bid = max(self.current_bid - 5, 0)
                    self._update_display()
                elif clicked:
                    # 进入出价确认状态
                    self.current_game_state = self.STATE_BID_CONFIRM
                    self._update_display()
            
            # Check auction end conditions (for AI turns)
            if player["is_ai"] and self.passes >= len(self.players) - 1:
                self._end_auction()
                
        elif self.current_game_state == self.STATE_BID_CONFIRM:
            # 确认或取消出价
            clicked = self.joystick.check_for_single_click()
            direction = self.joystick.get_direction(allow_repeat=False)
            
            if clicked:
                # 确认出价
                if self.current_bid > (self.current_bid if self.highest_bidder is None else 0):
                    self.highest_bidder = self.current_bidder_idx
                    self.passes = 0
                else:
                    self.passes += 1
                
                # Move to next bidder
                self.current_bidder_idx = (self.current_bidder_idx + 1) % len(self.players)
                self.current_game_state = self.STATE_AUCTION
                self._update_display()
            elif direction in ('left', 'right'):
                # 取消出价，返回拍卖界面
                self.current_game_state = self.STATE_AUCTION
                self._update_display()
            
            # Check auction end conditions
            if self.passes >= len(self.players) - 1:
                self._end_auction()
                
        elif self.current_game_state == self.STATE_ROUND_RESULT:
            if self.joystick.check_for_single_click():
                self._next_player()
                self.selected_item_idx = 0
                
                if self.current_game_state != self.STATE_GAME_OVER:
                    self.current_game_state = self.STATE_PLAYER_SELECT
                
                self._update_display()
                
        elif self.current_game_state == self.STATE_GAME_OVER:
            if self.joystick.check_for_single_click():
                return "GAME_ENDED_AUCTION"  # Signal to main.py to exit
        
        return None  # Game still running
    
    def _end_auction(self):
        """Handle auction completion"""
        if self.highest_bidder is not None and self.highest_bidder >= 0:
            # Winner pays and gets item
            winner = self.players[self.highest_bidder]
            seller = self.players[self.current_player_idx]
            
            winner["cash"] -= self.current_bid
            seller["cash"] += self.current_bid
            winner["items"].append(self.auction_item)
        else:
            # No bids, return to seller
            self.players[self.current_player_idx]["items"].append(self.auction_item)
        
        self.current_game_state = self.STATE_ROUND_RESULT
        self._update_display()

