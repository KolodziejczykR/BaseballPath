OUTFIELD_POSITIONS = ['OF']
INFIELD_POSITIONS = ['1B', '2B', '3B', 'SS']
PITCHER_POSITIONS = ['LHP', 'RHP']

class PlayerType:
    """ 
    Base class for player types in baseball recruitment.
    This class serves as a foundation for defining specific player types.

    This will be the parent class to all player types, such as Outfielder, Infielder, etc.
    Mandatory attributes include:
    - height: int -> Height of the player in inches
    - weight: int -> Weight of the player in pounds
    - primary_position: str -> Primary position of the player (e.g., 'OF', '1B', etc.)
    - region (str): Region of the player (e.g., 'West', 'South', 'Northeast', 'Midwest)

    These attributes are used for every player type, so it is defined here.
    """
    def __init__(self, height: int, weight: int, primary_position: str, region: str):
        self.height = height
        self.weight = weight
        self.region = region
        self.primary_position = primary_position

    def get_player_type(self) -> str:
        """
        Returns the type of player based on primary position.
        """
        return self.__class__.__name__

    def get_player_info(self) -> dict:
        return {
            "height": self.height,
            "weight": self.weight,
            "primary_position": self.primary_position,
            "region": self.region
        }
    
    def get_player_features(self) -> dict:
        return {
            "height": 'player height',
            "weight": 'player weight',
            "primary_position": 'player primary position',
            "region": 'player region (northeast, midwest, south, west)'
        }

class PlayerCatcher(PlayerType):
    def __init__(
        self,
        height: int,
        weight: int,
        primary_position: str,
        hitting_handedness: str,
        throwing_hand: str,
        region: str,
        exit_velo_max: float,
        c_velo: float,
        pop_time: float,
        sixty_time: float
    ):
        """
        Initialize a PlayerCatcher object.

        Parameters:
        height (int): Height of the player in inches
        weight (int): Weight of the player in pounds
        primary_position (str): Primary position of the player (e.g., 'C')
        hitting_handedness (str): Hitting handedness of the player (e.g., 'R', 'L', 'S')
        throwing_hand (str): Throwing hand of the player (e.g., 'L', 'R')
        region (str): Region of the player (e.g., 'West', 'South', 'Northeast', 'Midwest)
        c_velo (float): Catcher velocity (mph)
        pop_time (float): Pop time of the player (seconds)
        exit_velo_max (float): Maximum exit velocity (mph)
        """
        super().__init__(height, weight, region, primary_position)
        self.c_velo = c_velo
        self.pop_time = pop_time
        self.exit_velo_max = exit_velo_max
        self.sixty_time = sixty_time
        self.hitting_handedness = hitting_handedness
        self.throwing_hand = throwing_hand
    
    def get_player_type(self) -> str:
        return "Catcher"

    def get_player_features(self) -> dict:
        """
        Convert PlayerCatcher to dictionary format expected by ML models.
        """
        return {
            'height': 'player height',
            'weight': 'player weight',
            'sixty_time': 'player 60-yard dash time (ex 6.95 seconds)',
            'exit_velo_max': 'player exit velocity (mph)',
            'c_velo': 'player catcher velocity (mph)',
            'pop_time': 'player pop time (seconds)',
            'primary_position': 'player primary position (catcher)',
            'player_region': 'player region (northeast, midwest, south, west)',
            'throwing_hand': 'player throwing hand (left, right)',
            'hitting_handedness': 'player hitting handedness (left, right, switch)'
        }
    
    def get_player_info(self) -> dict:
        return {
            'height': self.height,
            'weight': self.weight,
            'sixty_time': self.sixty_time,
            'exit_velo_max': self.exit_velo_max,
            'c_velo': self.c_velo,
            'pop_time': self.pop_time,
            'primary_position': self.primary_position,
            'player_region': self.region,
            'throwing_hand': self.throwing_hand,
            'hitting_handedness': self.hitting_handedness
        }
    
    def __str__(self):
        """
        Returns a string representation of the PlayerCatcher object, showing its attributes in dictionary format.
        """
        return self.get_player_info().__str__()


class PlayerInfielder(PlayerType):
    def __init__(
        self,
        height: int,
        weight: int,
        primary_position: str,
        hitting_handedness: str,
        throwing_hand: str,
        region: str,
        exit_velo_max: float,
        inf_velo: float,
        sixty_time: float
    ):
        """
        Initialize a PlayerInfielder object.

        Parameters:
        height (int): Height of the player in inches
        weight (int): Weight of the player in pounds
        primary_position (str): Primary position of the player (e.g., '1B', '2B', '3B', 'SS')
        hitting_handedness (str): Hitting handedness of the player (e.g., 'R', 'L', 'S')
        throwing_hand (str): Throwing hand of the player (e.g., 'L', 'R')
        region (str): Region of the player (e.g., 'West', 'South', 'Northeast', 'Midwest)
        inf_velo (float): Infield velocity (mph)
        exit_velo_max (float): Maximum exit velocity (mph)
        """
        super().__init__(height, weight, region, primary_position)
        self.inf_velo = inf_velo
        self.exit_velo_max = exit_velo_max
        self.sixty_time = sixty_time
        self.hitting_handedness = hitting_handedness
        self.throwing_hand = throwing_hand

    def get_player_type(self) -> str:
        return "Infielder"
    
    def get_player_features(self) -> dict:
        """
        Convert PlayerInfielder to dictionary format expected by ML models.
        """
        return {
            'height': 'player height',
            'weight': 'player weight',
            'sixty_time': 'player 60-yard dash time (ex 6.95 seconds)',
            'exit_velo_max': 'player exit velocity (mph)',
            'inf_velo': 'player infield velocity (mph)',
            'primary_position': 'player primary position (1B, 2B, 3B, SS)',
            'player_region': 'player region (northeast, midwest, south, west)',
            'throwing_hand': 'player throwing hand (left, right)',
            'hitting_handedness': 'player hitting handedness (left, right, switch)'
        }

    def get_player_info(self) -> dict:
        """
        Convert PlayerInfielder to dictionary format expected by ML models.
        """
        return {
            'height': self.height,
            'weight': self.weight,
            'sixty_time': self.sixty_time,
            'exit_velo_max': self.exit_velo_max,
            'inf_velo': self.inf_velo,
            'primary_position': self.primary_position,
            'player_region': self.region,
            'throwing_hand': self.throwing_hand,
            'hitting_handedness': self.hitting_handedness
        }
    
    def __str__(self):
        """
        Returns string representation of the PlayerInfielder object, showing its attributes in dictionary format.
        """
        return self.get_player_info().__str__()


class PlayerOutfielder(PlayerType):
    def __init__(
        self,
        height: int,
        weight: int,
        primary_position: str,
        hitting_handedness: str,
        throwing_hand: str,
        region: str,
        exit_velo_max: float,
        of_velo: float,
        sixty_time: float
    ):
        """
        Initialize a PlayerOutfielder object.

        Parameters:
        height (int): Height of the player in inches
        weight (int): Weight of the player in pounds
        primary_position (str): Primary position of the player (e.g., 'OF')
        hitting_handedness (str): Hitting handedness of the player (e.g., 'R', 'L', 'S')
        throwing_hand (str): Throwing hand of the player (e.g., 'L', 'R')
        region (str): Region of the player (e.g., 'West', 'South', 'Northeast', 'Midwest)
        of_velo (float): Outfield velocity (mph)
        exit_velo_max (float): Maximum exit velocity (mph)
        sixty_time (float): 60-yard dash time (seconds)
        """
        super().__init__(height, weight, region, primary_position)
        self.of_velo = of_velo
        self.exit_velo_max = exit_velo_max
        self.sixty_time = sixty_time
        self.hitting_handedness = hitting_handedness
        self.throwing_hand = throwing_hand

    def get_player_type(self) -> str:
        return "Outfielder"
    
    def get_player_features(self) -> dict:
        """
        Convert PlayerOutfielder to dictionary format expected by ML models.
        """
        return {
            'height': 'player height',
            'weight': 'player weight',
            'sixty_time': 'player 60-yard dash time (ex 6.95 seconds)',
            'exit_velo_max': 'player exit velocity (mph)',
            'of_velo': 'player outfield velocity (mph)',
            'primary_position': 'player primary position (OF)',
            'player_region': 'player region (northeast, midwest, south, west)',
            'throwing_hand': 'player throwing hand (left, right)',
            'hitting_handedness': 'player hitting handedness (left, right, switch)'
        }

    def get_player_info(self) -> dict:
        """
        Convert PlayerOutfielder to dictionary format expected by ML models.
        """
        return {
            'height': self.height,
            'weight': self.weight,
            'sixty_time': self.sixty_time,
            'exit_velo_max': self.exit_velo_max,
            'of_velo': self.of_velo,
            'player_region': self.region,
            'throwing_hand': self.throwing_hand,
            'hitting_handedness': self.hitting_handedness
        }
    
    def __str__(self):
        """
        Returns string representation of the PlayerOutfielder object, showing its attributes in dictionary format.
        """
        return self.get_player_info().__str__()


class PlayerPitcher(PlayerType):
    def __init__(
            self,
            height: int,
            weight: int,
            primary_position: str,
            throwing_hand: str,
            region: str,
            fastball_velo_range: float = None,
            fastball_velo_max: float = None,
            fastball_spin: float = None,
            changeup_velo: float = None,
            changeup_spin: float = None,
            curveball_velo: float = None,
            curveball_spin: float = None,
            slider_velo: float = None,
            slider_spin: float = None
        ):
        super().__init__(height, weight, region, primary_position)
        self.throwing_hand = throwing_hand
        self.fastball_velo_range = fastball_velo_range
        self.fastball_velo_max = fastball_velo_max
        self.fastball_spin = fastball_spin
        self.changeup_velo = changeup_velo
        self.changeup_spin = changeup_spin
        self.curveball_velo = curveball_velo
        self.curveball_spin = curveball_spin
        self.slider_velo = slider_velo
        self.slider_spin = slider_spin

    def get_player_type(self) -> str:
        return "Pitcher"

    def get_player_features(self) -> dict:
        return {
            'height': 'player height',
            'weight': 'player weight',
            'primary_position': 'player primary position (RHP/LHP)',
            'player_region': 'player region (northeast, midwest, south, west)',
            'throwing_hand': 'player throwing hand (left, right)',
            'fastball_velo_range': 'fastball velo range (mph)',
            'fastball_velo_max': 'fastball max velo (mph)',
            'fastball_spin': 'fastball spin rate (rpm)',
            'changeup_velo': 'changeup velo (mph)',
            'changeup_spin': 'changeup spin (rpm)',
            'curveball_velo': 'curveball velo (mph)',
            'curveball_spin': 'curveball spin (rpm)',
            'slider_velo': 'slider velo (mph)',
            'slider_spin': 'slider spin (rpm)',
        }

    def get_player_info(self) -> dict:
        return {
            'height': self.height,
            'weight': self.weight,
            'primary_position': self.primary_position,
            'player_region': self.region,
            'throwing_hand': self.throwing_hand,
            # snake_case keys
            'fastball_velo_range': self.fastball_velo_range,
            'fastball_velo_max': self.fastball_velo_max,
            'fastball_spin': self.fastball_spin,
            'changeup_velo': self.changeup_velo,
            'changeup_spin': self.changeup_spin,
            'curveball_velo': self.curveball_velo,
            'curveball_spin': self.curveball_spin,
            'slider_velo': self.slider_velo,
            'slider_spin': self.slider_spin,
            # CSV-style keys for compatibility
            'FastballVelo (avg)': self.fastball_velo_range,
            'FastballVelocity (max)': self.fastball_velo_max,
            'FastballSpin Rate (avg)': self.fastball_spin,
            'Changeup Velo Range': self.changeup_velo,
            'Changeup Spin Rate (avg)': self.changeup_spin,
            'Curveball Velo Range': self.curveball_velo,
            'Curveball Spin Rate (avg)': self.curveball_spin,
            'Slider Velo Range': self.slider_velo,
            'Slider Spin Rate (avg)': self.slider_spin,
        }

    def __str__(self):
        return self.get_player_info().__str__()
    
