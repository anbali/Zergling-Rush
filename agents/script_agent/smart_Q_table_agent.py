"""reference: https://chatbotslife.com/building-a-smart-pysc2-agent-cdc269cb095d

this agent make decision using Q Learning, again, this is for learning / warm up practices

running this agent:
python -m pysc2.bin.agent \
--map BuildMarines \
--agent smart_Q_table_agent.SmartAgent \
--agent_race terran \
--max_agent_steps 0 \
--norender

this agent is modified for just build marine

description:
the agent follow a determinstic patten and build two depot, one barrack and 19 marines in the first two episode.

It might trap in a local minimum.
"""

import random
import math
import numpy as np
import pandas as pd
import time


from pysc2.agents import base_agent
from pysc2.lib import actions
from pysc2.lib import features

# function id, unit id, feature id, parameter
_NO_OP = actions.FUNCTIONS.no_op.id
_SELECT_POINT = actions.FUNCTIONS.select_point.id
_BUILD_SUPPLY_DEPOT = actions.FUNCTIONS.Build_SupplyDepot_screen.id
_BUILD_BARRACKS = actions.FUNCTIONS.Build_Barracks_screen.id
_TRAIN_MARINE = actions.FUNCTIONS.Train_Marine_quick.id
# _SELECT_ARMY = actions.FUNCTIONS.select_army.id
# _ATTACK_MINIMAP = actions.FUNCTIONS.Attack_minimap.id

_PLAYER_RELATIVE = features.SCREEN_FEATURES.player_relative.index
_UNIT_TYPE = features.SCREEN_FEATURES.unit_type.index
_PLAYER_ID = features.SCREEN_FEATURES.player_id.index

_PLAYER_SELF = 1

_TERRAN_COMMANDCENTER = 18
_TERRAN_SCV = 45
_TERRAN_SUPPLY_DEPOT = 19
_TERRAN_BARRACKS = 21
_TERRAN_MARINE = 48

_NOT_QUEUED = [0]
_QUEUED = [1]

# define reward
# KILL_UNIT_REWARD = 0.2
# KILL_BUILDING_REWARD = 0.5
BUILD_MARINE_REWARD = 0.5
BUILD_BARRACK_REWARD = 1
BUILD_DEPOT_REWARD = 0.5


# define actions for this agent
ACTION_DO_NOTHING = 'donothing'
ACTION_SELECT_SCV = 'selectscv'
ACTION_BUILD_SUPPLY_DEPOT = 'buildsupplydepot'
ACTION_BUILD_BARRACKS = 'buildbarracks'
ACTION_SELECT_BARRACKS = 'selectbarracks'
ACTION_BUILD_MARINE = 'buildmarine'
# ACTION_SELECT_ARMY = 'selectarmy'
# ACTION_ATTACK = 'attack'

smart_actions = [
    ACTION_DO_NOTHING,
    ACTION_SELECT_SCV,
    ACTION_BUILD_SUPPLY_DEPOT,
    ACTION_BUILD_BARRACKS,
    ACTION_SELECT_BARRACKS,
    ACTION_BUILD_MARINE,
    # ACTION_SELECT_ARMY,
    # ACTION_ATTACK,
]


class QLearningTable:
    def __init__(self, actions, learning_rate=0.01, reward_decay=0.9, e_greedy=0.9):
        self.actions = actions
        self.lr = learning_rate
        self.gamma = reward_decay
        self.epsilon = e_greedy
        self.q_table = pd.DataFrame(columns=self.actions, dtype=np.float64)

    def choose_action(self, observation):
        self.check_state_exist(observation)

        if np.random.uniform() < self.epsilon:
            # dataframe.ix can use either index or label to get cell data
            state_action = self.q_table.ix[observation, :]

            # some actions has same value
            # .index are the row name
            state_action = state_action.reindex(np.random.permutation(state_action.index))

            return state_action.idxmax()

        else:
            return np.random.choice(self.actions)

    def learn(self, s, a, r, s_):
        self.check_state_exist(s_)
        self.check_state_exist(s)

        q_predict = self.q_table.ix[s, a]
        q_target = r + self.gamma * self.q_table.ix[s_, :].max()

        # update
        self.q_table.ix[s, a] += self.lr * (q_target - q_predict)
        pass

    def check_state_exist(self, state):
        if state not in self.q_table.index:
            # add new state to q_table
            self.q_table = self.q_table.append(pd.Series([0] * len(self.actions), index=self.q_table.columns, name=state))
        pass


class SmartAgent(base_agent.BaseAgent):

    def __init__(self):
        super(SmartAgent, self).__init__()
        self.qlearn = QLearningTable(actions=list(range(len(smart_actions)))) # 0, 1, 2 ...

        # R, s, a
        # self.previous_killed_unit_score = 0
        # self.previous_killed_building_score = 0
        self.previous_barrack_unit_score = 0
        self.previous_depot_unit_score = 0
        self.previous_marine_unit_score = 0

        self.previous_action = None
        self.previous_state = None

    def transformLocation(self, x, x_distance, y, y_distance):
        if not self.base_top_left:
            return [x - x_distance, y - y_distance]
        return [x + x_distance, y + y_distance]

    def get_num_marines(self, obs):
        unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
        unit_y, unit_x = (unit_type == _TERRAN_MARINE).nonzero()
        num_unit = int(len(np.unique(unit_y)))
        # print(num_unit)
        return num_unit
        pass

    def get_num_depots(self, obs):
        unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
        unit_y, unit_x = (unit_type == _TERRAN_SUPPLY_DEPOT).nonzero()
        num_unit = int(len(np.unique(unit_y)))
        return num_unit
        pass

    def get_num_barrack(self, obs):
        unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
        unit_y, unit_x = (unit_type == _TERRAN_BARRACKS).nonzero()

        num_unit = int(len(np.unique(unit_y)))
        return num_unit
        pass

    def step(self, obs):
        super(SmartAgent, self).step(obs)

        print(obs.observation.player.army_count)

        random.seed(time.time())

        player_y, player_x = (obs.observation['feature_minimap'][_PLAYER_RELATIVE] == _PLAYER_SELF).nonzero()
        self.base_top_left = 1 if player_y.any() and player_y.mean() <= 31 else 0

        # get depot count and barrack count as state features
        unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
        depot_y, depot_x = (unit_type == _TERRAN_SUPPLY_DEPOT).nonzero()
        supply_depot_count = 1 if depot_y.any() else 0

        barracks_y, barracks_x = (unit_type == _TERRAN_SUPPLY_DEPOT).nonzero()
        barracks_count = 1 if barracks_y.any() else 0

        supply_limit = obs.observation['player'][4]
        army_supply = obs.observation['player'][5]

        # define state tuple
        current_state = [
            supply_depot_count,
            barracks_count,
            supply_limit,
            army_supply,
        ]

        # get previous reward
        # killed_unit_score = obs.observation['score_cumulative'][5]
        # killed_building_score = obs.observation['score_cumulative'][6]
        marine_unit_score = self.get_num_marines(obs)
        depot_unit_score = self.get_num_depots(obs)
        barrack_unit_score = self.get_num_barrack(obs)

        # don't learn from 1st step
        if self.previous_action is not None:
            reward = 0
            # calculate reward
            # if killed_unit_score > self.previous_killed_building_score:
            #     reward += KILL_UNIT_REWARD
            # if killed_building_score > self.previous_killed_building_score:
            #     reward += KILL_BUILDING_REWARD

            if marine_unit_score > self.previous_marine_unit_score:
                reward += BUILD_MARINE_REWARD
            if depot_unit_score > self.previous_depot_unit_score:
                reward += BUILD_DEPOT_REWARD
            if barrack_unit_score > self.previous_barrack_unit_score:
                reward += BUILD_BARRACK_REWARD

            # learn
            self.qlearn.learn(str(self.previous_state), self.previous_action, reward, str(current_state))

        rl_action = self.qlearn.choose_action(str(current_state))
        smart_action = smart_actions[rl_action]

        # self.previous_killed_unit_score = killed_unit_score
        # self.previous_killed_building_score = killed_building_score
        self.previous_barrack_unit_score = barrack_unit_score
        self.previous_depot_unit_score = depot_unit_score
        self.previous_marine_unit_score = marine_unit_score
        self.previous_state = current_state
        self.previous_action = rl_action

        if smart_action == ACTION_DO_NOTHING:
            return actions.FunctionCall(_NO_OP, [])

        elif smart_action == ACTION_SELECT_SCV:
            unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
            unit_y, unit_x = (unit_type == _TERRAN_SCV).nonzero()

            if unit_y.any():
                # randomly select a worker to be selected
                i = random.randint(0, len(unit_y) - 1)
                target = [unit_x[i], unit_y[i]]
                return actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, target])

        elif smart_action == ACTION_BUILD_SUPPLY_DEPOT:
            if _BUILD_SUPPLY_DEPOT in obs.observation["available_actions"]:
                unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
                unit_y, unit_x = (unit_type == _TERRAN_COMMANDCENTER).nonzero()

                if unit_y.any():
                    target = self.transformLocation(int(unit_x.mean()), 0, int(unit_y.mean()), random.randint(5, 20))
                    return actions.FunctionCall(_BUILD_SUPPLY_DEPOT, [_NOT_QUEUED, target])

        elif smart_action == ACTION_BUILD_BARRACKS:
            if _BUILD_BARRACKS in obs.observation['available_actions']:
                unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
                unit_y, unit_x = (unit_type == _TERRAN_COMMANDCENTER).nonzero()

                if unit_y.any():
                    target = self.transformLocation(int(unit_x.mean()), random.randint(5, 20), int(unit_y.mean()), 0)
                    return actions.FunctionCall(_BUILD_BARRACKS, [_NOT_QUEUED, target])
            pass

        elif smart_action == ACTION_SELECT_BARRACKS:
            unit_type = obs.observation['feature_screen'][_UNIT_TYPE]
            unit_y, unit_x = (unit_type == _TERRAN_BARRACKS).nonzero()
            if unit_y.any():
                target = [int(unit_x.mean()), int(unit_y.mean())]
                return actions.FunctionCall(_SELECT_POINT, [_NOT_QUEUED, target])
            pass

        elif smart_action == ACTION_BUILD_MARINE:
            if _TRAIN_MARINE in obs.observation['available_actions']:
                return actions.FunctionCall(_TRAIN_MARINE, [_QUEUED])
            pass

        # elif smart_action == ACTION_SELECT_ARMY:
        #     if _SELECT_ARMY in obs.observation['available_actions']:
        #         return actions.FunctionCall(_SELECT_ARMY, [_NOT_QUEUED])
        #     pass
        # elif smart_action == ACTION_ATTACK:
        #     if _ATTACK_MINIMAP in obs.observation["available_actions"]:
        #         if self.base_top_left:
        #             return actions.FunctionCall(_ATTACK_MINIMAP, [_NOT_QUEUED, [39, 45]])
        #         return actions.FunctionCall(_ATTACK_MINIMAP, [_NOT_QUEUED, [21, 24]])
        #     pass

        return actions.FunctionCall(_NO_OP, [])
