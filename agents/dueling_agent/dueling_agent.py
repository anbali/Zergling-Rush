#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
introduction: this agent use a dueling deep q network
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf
import tensorflow.contrib.layers as layers

from pysc2.agents import base_agent
from pysc2.lib import actions
from pysc2.lib import features

from .utils import preprocess_screen, screen_channel

_PLAYER_RELATIVE = features.PlayerRelative.ALLY


class DuelingAgent(object):

    def __init__(self):
        self.reward = 0
        self.episodes = 0
        self.steps = 0
        self.obs_spec = None
        self.action_spec = None
        self.isize = len(actions.FUNCTIONS)
        pass

    def setup(
            self,
            obs_spec,
            action_spec,
            screen_size,
            learning_rate=0.001,
            reward_decay=0.9,
            e_greedy=0.9,
            replace_target_iter=200,
            memory_size=500,
            batch_size=32,
            e_greedy_increment=None,
            output_graph=False,
            sess=None
    ):
        """
        1. this function is run before the episode iteration starts
        2. set up tf session, network structure with input args,
        experience replay storage and optimizer for training
        """
        self.obs_spec = obs_spec
        self.action_spec = action_spec

        # learning setting
        self.ssize = screen_size # input cnn size
        self.lr = learning_rate
        self.gamma = reward_decay
        self.epsilon_max = e_greedy
        self.replace_target_iter = replace_target_iter
        self.memory_size = memory_size
        self.batch_size = batch_size
        self.epsilon_increment = e_greedy_increment
        self.epsilon = 0 if e_greedy_increment is not None else self.epsilon_max

        self.learn_step_counter = 0
        self.memory = np.zeros((self.memory_size, self.ssize*2+2))

        # build model
        self.build_model()

        # this operation is for replace target net params with eval net params
        # t_params = tf.get_collection('target_net_params')
        # e_params = tf.get_collection('eval_net_params')
        t_params = tf.get_collection(key=tf.GraphKeys.GLOBAL_VARIABLES, scope='target_net')
        e_params = tf.get_collection(key=tf.GraphKeys.GLOBAL_VARIABLES, scope='eval_net')
        self.replace_target_op = [tf.assign(ref=t, value=e) for t, e in zip(t_params, e_params)]

        # init tf session
        self.init_session(sess=sess, output_graph=output_graph)

    def init_session(self, sess, output_graph):
        """handle tf session setup, tf log and tf graph"""
        # set up session
        if sess is None:
            self.sess = tf.Session()
            self.sess.run(tf.global_variables_initializer())
        else:
            self.sess = sess
        if output_graph:
            tf.summary.FileWriter("logs/", self.sess.graph)
        pass

    def build_network(self):
        """
        define convolution network layers (two conv, two pool, one fully-connected)
        two cnn nets with above config and
        input: screen feature

        [None, screen_channel(), self.ssize, self.ssize] -> [None, self.ssize, self.ssize, screen_channel()]
        traditional input dims:  Batch  size x  Height  x  Width  x  Channels
        tradition weight: Height  x  Width  x  Input   Channels  x  Output   Channels
        output: spatial action output, non-spatial action output


        """

        # Extract features

        sconv1 = tf.layers.conv2d(
            inputs=tf.transpose(a=self.screen, perm=[0, 2, 3, 1]),
            filters=16,
            kernel_size=[5, 5],
            strides=[1, 1],
            padding='same',
            activation=tf.nn.relu,
            name='sconv1'   # 1st conv2d feature layer
        )

        # pooling can be inserted here

        sconv2 = tf.layers.conv2d(
            inputs=sconv1,
            filters=32,
            kernel_size=[3, 3],
            strides=[1, 1],
            padding='same',
            activation=tf.nn.relu,
            name='sconv2')  # 2nd conv2d feature layer

        # Compute spatial actions
        # feat_conv = tf.concat([sconv2], axis=3) # concat minimap and screen on channel dimension

        spatial_action = tf.layers.conv2d(
            inputs=sconv2,
            filters=1,
            kernel_size=[1, 1],
            strides=(1, 1),
            padding='same',
            activation=None,
            name='saptial_action')
        spatial_action = tf.nn.softmax(tf.layers.flatten(spatial_action))

        # Compute non spatial actions and value
        info_fc = tf.layers.dense(
            inputs=tf.layers.flatten(inputs=self.info),
            units=256,
            activation=tf.tanh,
            name='info_fc')

        feat_fc = tf.concat([layers.flatten(sconv2), info_fc], axis=1)
        feat_fc = tf.layers.dense(
            inputs=feat_fc,
            units=256,
            activation=tf.nn.relu,
            name='feat_fc')
        non_spatial_action = tf.layers.dense(inputs=feat_fc,
                                             units=len(actions.FUNCTIONS),
                                             activation=tf.nn.softmax,
                                             name='non_spatial_action')

        q = tf.reshape(
            tensor=tf.layers.dense(
                inputs=feat_fc,
                units=1,
                activation=None,
                name='q'),
            shape=[-1])

        return spatial_action, non_spatial_action, q

    def build_model(self):
        """
        define evaluation net, target net
        define optimizer for evaluation net
        """

        # ---------------------------evaluation net for spatial, non-spatial---------------------------
        # cnn input features
        self.screen = tf.placeholder(tf.float32, [None, screen_channel(), self.ssize, self.ssize], name='screen')
        self.info = tf.placeholder(tf.float32, [None, self.isize], name='info')
        # build eval net for spatial, non-spatial and return q_eval scope name = eval_net, collection name = eval...
        with tf.variable_scope('eval_net'):
            # c_name = ['eval_net_params', tf.GraphKeys.GLOBAL_VARIABLES]
            self.spatial_action, self.non_spatial_action, self.q_eval = self.build_network()

        # ---------------------------target net for spatial, non-spatial---------------------------

        pass

    def reset(self):
        """reward discount reset"""
        self.episodes += 1

    def step(self, obs):
        """
        get observation, return action using RL
        obs = observation spec in lib/features.py : 218
        """

        # obs.observation.screen_feature is (17, 64, 64)
        screen = np.array(obs.observation.feature_screen, dtype=np.float32)
        screen_input = np.expand_dims(preprocess_screen(screen), axis=0) # return (bs=1, channel=42, h=64, w=64)
        # print("input shape: ", screen_input.shape)
        self.steps += 1
        self.reward += obs.reward
        return actions.FunctionCall(actions.FUNCTIONS.no_op.id, [])

    def store_transition(self, obs, a, obs_):
        """store the transition in experience replay"""

        pass

    def learn(self):
        """when certain number of replay size reach, learn from minibatch replay"""
        pass

# if __name__ == '__main__':
#     agent = DuelingAgent()
#     agent.setup(
#         obs_spec=1,
#         action_spec=1,
#         screen_size=64,
#         learning_rate=0.001,
#         reward_decay=0.9,
#         e_greedy=0.9,
#         replace_target_iter=200,
#         memory_size=2000,
#         batch_size=32,
#         e_greedy_increment=None,
#         output_graph=False,
#         sess=None
#     )
#
#     # print([n.name for n in tf.get_default_graph().as_graph_def().node])
#     agent.sess.run(agent.replace_target_op)
#     print(tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,scope='target_net'))



