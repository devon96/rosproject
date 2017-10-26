#!/usr/bin/env python2
import rospy
import tf
import numpy as np
import math
import pickle
import heapq
from itertools import chain
from geometry_msgs.msg import Point, Twist
from visualization_msgs.msg import Marker, MarkerArray
from nav_msgs.msg import OccupancyGrid, Odometry


class Node:  # helper classes for both graph and nodes to make the representation easier
    def __init__(self, name, x_coord, y_coord):
        self.name = name
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.neighbours = {}

    def add_neighbour(self, neighbour, cost):
        self.neighbours[neighbour] = cost

    def get_weight(self, neighbour):
        return self.neighbours[neighbour]

    def get_neighbours(self):
        return self.neighbours.keys()

    def get_name(self):
        return self.name


class Graph:
    def __init__(self):
        self.nodes = {}
        self.num_nodes = 0

    def add_node(self, vertex, x_coord, y_coord):
        new_node = Node(vertex, x_coord, y_coord)
        self.num_nodes += 1
        self.nodes[vertex] = new_node

    def get_node(self, vertex):
        return self.nodes[vertex]

    def add_edge(self, s, s_x, s_y, t, t_x, t_y, cost):
        if s not in self.nodes:
            self.add_node(s, s_x, s_y)
        if t not in self.nodes:
            self.add_node(t, t_x, t_y)
        self.nodes[s].add_neighbour(self.nodes[t], cost)

    def get_nodes(self):
        return self.nodes.keys()


def heuristic_estimate(start, end):
    s_x = start.x_coord
    s_y = start.y_coord
    f_x = end.x_coord
    f_y = end.y_coord

    return math.sqrt(abs(s_x - f_x)**2 + abs(s_y - f_y)**2)


class myRobot():
    def __init__(self):

        self.cells_array = pickle.load(open("/home/konrad/cells.pickle", "rb"))

        self.neighbours = pickle.load(
            open("/home/konrad/neighbours.pickle", "rb"))

        self.path = []

        self.goal = rospy.get_param("goal3")

        self.graph = Graph()

        self.init_graph()

        self.rviz_pub = rospy.Publisher(
            "/robot_model", MarkerArray, queue_size=10)

        self.rviz_map_pub = rospy.Publisher(
            "/real_robot_pose", OccupancyGrid, queue_size=10)

        self.cells_pub = rospy.Publisher(
            "/cells_boxes", MarkerArray, queue_size=10)

        self.path_pub = rospy.Publisher(
            "/calculated_path", MarkerArray, queue_size=10)

        self.goals_pub = rospy.Publisher(
            "/goals_models", MarkerArray, queue_size=10)

        self.ground_pose_sub = rospy.Subscriber(
            "/base_pose_ground_truth", Odometry, self.get_pose)

        self.map_sub = rospy.Subscriber("/map", OccupancyGrid, self.get_map)

        self.tf_listener = tf.TransformListener()

        self.robot_pose = Odometry()

    def init_graph(self):

        for i in range(0, len(self.cells_array)):
            self.graph.add_node(
                i, self.cells_array[i][0], self.cells_array[i][1])

        # Go through all identified cells.
        for i in range(0, len(self.cells_array)):
            # And for every cell, go through its neighbours.
            for j in range(0, len(self.neighbours[i])):
                dist_x = abs(
                    self.cells_array[i][0] - self.cells_array[list(self.neighbours[i])[j]][0])
                dist_y = abs(
                    self.cells_array[i][1] - self.cells_array[list(self.neighbours[i])[j]][1])
                s_x = self.cells_array[i][0]
                s_y = self.cells_array[i][1]
                t_x = self.cells_array[list(self.neighbours[i])[j]][0]
                t_y = self.cells_array[list(self.neighbours[i])[j]][1]

                self.graph.add_edge(
                    i, s_x, s_y, list(self.neighbours[i])[j], t_x, t_y, math.sqrt(dist_x**2 + dist_y**2))

    def find_shortest_path(self, s, t):

        start = self.graph.get_node(s)
        finish = self.graph.get_node(t)
        closedset = []
        came_from = {}
        g_score = {}
        g_score[start] = 0
        f_score = {}
        f_score[start] = g_score[start] + heuristic_estimate(start, finish)
        openset = [[f_score[start], start]]
        heapq.heapify(openset)

        while openset:
            current = heapq.heappop(openset)[1]
            if current == finish:
                break

            closedset.append(current)

            for neighbour in current.get_neighbours():

                if neighbour in closedset:
                    continue

                tentative_g_score = g_score[current] + \
                    current.get_weight(neighbour)

                if neighbour not in openset or tentative_g_score < g_score[neighbour]:
                    came_from[neighbour] = current
                    g_score[neighbour] = tentative_g_score
                    f_score[neighbour] = g_score[neighbour] + \
                        heuristic_estimate(neighbour, finish)

                    if neighbour not in list(chain.from_iterable(openset)):
                        heapq.heappush(
                            openset, [f_score[neighbour], neighbour])
                    else:
                        index = [i for i, x in enumerate(
                            openset) if x[1] == neighbour][0]
                        openset[index][0] = f_score[neighbour]

        current = finish
        total_path = [finish]

        while current != start:
            current = came_from[current]
            total_path.append(current)

        total_path = total_path[1:-1]
        self.path = total_path

    def get_map(self, data):
        self.mapgrid = data
        self.start_x = data.info.origin.position.x
        self.start_y = data.info.origin.position.y
        self.resolution = data.info.resolution

    def get_pose(self, robot_pose):
        self.robot_pose = robot_pose

    def draw_self(self):
        mr = Marker()
        mr.header.frame_id = "/map"
        mr.ns = "basic"
        mr.id = 2
        mr.type = mr.CUBE
        mr.action = mr.ADD
        mr.pose.position.x = self.robot_pose.pose.pose.position.x - 0.05
        mr.pose.position.y = self.robot_pose.pose.pose.position.y
        mr.pose.position.z = 0.05
        mr.pose.orientation = self.robot_pose.pose.pose.orientation
        mr.scale.x = 0.1
        mr.scale.y = 0.1
        mr.scale.z = 0.1
        mr.color.r = 0
        mr.color.g = 0
        mr.color.b = 1
        mr.color.a = 1.0
        ma = MarkerArray()
        ma.markers.append(mr)
        self.rviz_pub.publish(ma)

    def find_closest_cell(self, x, y):
        min_dist = 9999
        cell_index = -1
        ite = 0
        for i in self.cells_array:
            dist = math.sqrt(i[0]**2 + i[1]**2)
            if((dist < min_dist) and
               (x in range(i[0] - i[2] / 2, i[0] + i[2] / 2) and
                    (y in range(i[1] - i[3] / 2, i[1] + i[3] / 2)))):
                cell_index = ite
                min_dist = dist
            ite += 1
        return cell_index

    def draw_path(self, sx, sy, fx, fy, id_num):

        cell_y = 0

        if sy < 0:
            cell_y = abs(sy) + 4.8
        else:
            cell_y = abs(sy - 4.8)

        sx_coord = int(round((sx + 6.0) / self.resolution))
        sy_coord = int(round((cell_y) / self.resolution))

        if fy < 0:
            cell_y = abs(fy) + 4.8
        else:
            cell_y = abs(fy - 4.8)

        fx_coord = int(round((fx + 6.0) / self.resolution))
        fy_coord = int(round((cell_y) / self.resolution))

        self.find_shortest_path(self.find_closest_cell(
            sy_coord, sx_coord), self.find_closest_cell(fy_coord, fx_coord))

        ma = MarkerArray()
        mr = Marker()
        mr.header.frame_id = "/map"
        mr.ns = "path"
        mr.id = id_num
        mr.type = mr.LINE_STRIP
        mr.action = mr.ADD

        mr.points = []

        mr.points.append(Point(x=fx, y=fy))

        for node in self.path:
            y_coord = -self.start_y - \
                (self.cells_array[node.get_name()][0] * self.resolution)
            x_coord = self.start_x + \
                (self.cells_array[node.get_name()][1] * self.resolution)
            mr.points.append(Point(x=x_coord, y=y_coord))
        mr.points.append(Point(x=sx, y=sy))

        mr.scale.x = 0.02

        mr.color.r = 1
        mr.color.g = 0
        mr.color.b = 0
        mr.color.a = 1.0
        ma = MarkerArray()
        ma.markers.append(mr)

        self.path_pub.publish(ma)

    def draw_odom(self):

        odom_pose = self.tf_listener.lookupTransform(
            "/map", "/odom", rospy.Time(0))

        mr = Marker()
        mr.header.frame_id = "/map"
        mr.ns = "odom_pose"
        mr.id = 1
        mr.type = mr.CUBE
        mr.action = mr.ADD
        mr.pose.position.x = odom_pose[0][0] - 0.05
        mr.pose.position.y = odom_pose[0][1]
        mr.pose.position.z = 0.05
        mr.pose.orientation.x = odom_pose[1][0]
        mr.pose.orientation.y = odom_pose[1][1]
        mr.pose.orientation.z = odom_pose[1][2]
        mr.pose.orientation.w = odom_pose[1][3]
        mr.scale.x = 0.1
        mr.scale.y = 0.1
        mr.scale.z = 0.1
        mr.color.r = 1
        mr.color.g = 0
        mr.color.b = 0
        mr.color.a = 1.0
        ma = MarkerArray()
        ma.markers.append(mr)
        self.rviz_pub.publish(ma)

    def draw_goals(self, sx, sy):

        cur_x = sx
        cur_y = sy

        ma = MarkerArray()
        for i in range(5):
            rospy.get_param("/goal" + str(i))[0]

            robot.draw_path(cur_x, cur_y, rospy.get_param(
                "/goal" + str(i))[0], rospy.get_param("/goal" + str(i))[1], i + 1)

            cur_x = rospy.get_param("/goal" + str(i))[0]
            cur_y = rospy.get_param("/goal" + str(i))[1]

            mr = Marker()
            mr.header.frame_id = "/map"
            mr.ns = "goals"
            mr.id = i
            mr.type = mr.CUBE
            mr.action = mr.ADD
            mr.pose.position.x = rospy.get_param("/goal" + str(i))[0] - 0.05
            mr.pose.position.y = rospy.get_param("/goal" + str(i))[1]
            mr.pose.position.z = 0.05
            mr.scale.x = 0.1
            mr.scale.y = 0.1
            mr.scale.z = 0.1
            mr.color.r = 0
            mr.color.g = 1
            mr.color.b = 0
            mr.color.a = 1.0
            ma.markers.append(mr)

        self.goals_pub.publish(ma)


if __name__ == '__main__':
    try:
        rospy.init_node('my_robot_node', anonymous=True)
        vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        robot = myRobot()

        rate = rospy.Rate(5)

        while not rospy.is_shutdown():

            tw = Twist()
            # tw.linear.x = 0.1
            vel_pub.publish(tw)

            try:
                robot.draw_self()
                robot.draw_odom()
                robot.draw_goals(-4.8, -3.6)
            except Exception as e:
                print e
            rate.sleep()

    except rospy.ROSInterruptException:
        pass