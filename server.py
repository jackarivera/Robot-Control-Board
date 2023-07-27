from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
import folium
import pandas as pd
import os
import json
from queue import Queue
import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, Imu
from pyquaternion import Quaternion
import time
import numpy as np

gps_queue = Queue()
imu_queue = Queue()

class SimpleNode(Node):
    def __init__(self):
        super().__init__("webserver_node")
        self.gps_subscriber = self.create_subscription(
            NavSatFix, "/gps/filtered", self.gps_callback, 10)
        self.imu_subscriber = self.create_subscription(
            Imu, "/imu/data", self.imu_callback, 10)
        self.offset = 90
        self.previous_yaw = 0

    def gps_callback(self, msg):
        gps_queue.put((msg.latitude, msg.longitude))

    def imu_callback(self, msg):
        orientation_q = msg.orientation
        quaternion = Quaternion(orientation_q.w, orientation_q.x, orientation_q.y, orientation_q.z).yaw_pitch_roll
        yaw, pitch, roll = quaternion
        yaw_d, pitch_d, roll_d = map(np.degrees, [yaw, pitch, roll])
        adjusted_yaw_d = self.adjust_angles(yaw_d)
        smoothed_yaw_d = self.smooth_yaw(adjusted_yaw_d)
        imu_queue.put(smoothed_yaw_d)

    def adjust_angles(self, angle):
        """Adjusts angles from [-180, 180] to [0, 360]."""
        angle += self.offset
        if angle < 0:
            angle += 360
        elif angle > 360:
            angle -= 360
        return angle

    def smooth_yaw(self, yaw):
        """Avoids jumps in yaw value."""
        diff = yaw - self.previous_yaw
        if abs(diff) > 180:
            if diff > 0:
                yaw -= 360
            else:
                yaw += 360
        self.previous_yaw = yaw
        return yaw


def ros_spin(node):
    rclpy.spin(node)


rclpy.init(args=None)
node = SimpleNode()
ros_thread = threading.Thread(target=ros_spin, args=(node,))
ros_thread.start()

def send_data_to_client():
    while True:
        while not gps_queue.empty():
            lat, lng = gps_queue.get()
            socketio.emit('gps_data', {'lat': lat, 'lng': lng})
        while not imu_queue.empty():
            rotation = imu_queue.get()
            socketio.emit('imu_data', {'rotation': rotation})
        time.sleep(0.1)  # adjust the sleep time as needed

send_thread = threading.Thread(target=send_data_to_client, daemon=True)
send_thread.start()

app = Flask(__name__, static_url_path='/static', static_folder='static')
coordinates = []

app.config['SECRET_KEY'] = 'your secret key'
socketio = SocketIO(app)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def index():
    global coordinates
    start_coords = (44.969450606801836, -93.5174435377121)
    folium_map = folium.Map(location=start_coords, zoom_start=24)
    folium_map.save('templates/map.html')
    coordinates = []
    return render_template('index.html')

@app.route('/add_waypoint', methods=['POST'])
def add_waypoint():
    global coordinates
    data = request.get_json()
    coordinates.append((data['lat'], data['lng']))
    print(coordinates)
    return 'Added waypoint: [' + str(data['lat']) + ', ' + str(data['lng']) + '] successfully', 200

@app.route('/update_waypoint', methods=['POST'])
def update_waypoint():
    global coordinates
    data = request.get_json()
    index = coordinates.index((data['old_lat'], data['old_lng']))
    coordinates.remove((data['old_lat'], data['old_lng']))
    coordinates.insert(index, (data['new_lat'], data['new_lng']))
    print(coordinates)
    return 'Updated waypoint: [' + str(data['new_lat']) + ', ' + str(data['new_lng']) + '] -> ' + '[' + str(data['new_lat']) + ', ' + str(data['new_lng']) + '] successfully', 200

@app.route('/del_waypoint', methods=['POST'])
def del_waypoint():
    global coordinates
    data = request.get_json()
    coordinates.remove((data['lat'], data['lng']))
    print(coordinates)
    return 'Deleted waypoint: [' + str(data['lat']) + ', ' + str(data['lng']) + '] successfully', 200

@app.route('/export_waypoints', methods=['POST'])
def export_waypoints():
    global coordinates
    print(coordinates)
    data = request.get_json()
    file_name = data['file_name']
    folder_path = os.path.join(".", "waypoints")
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Use os.path.join() to construct the file path within the 'waypoints' folder
    file_path = os.path.join(folder_path, str(file_name) + ".csv")
    df = pd.DataFrame(coordinates, columns=['Latitude', 'Longitude'])
    df.to_csv(file_path, index=False)
    return 'Exported waypoints', 200

@app.route('/clear_waypoints', methods=['GET'])
def clear_waypoints():
    global coordinates
    coordinates = []
    print(coordinates)
    return 'Cleared waypoints', 200

@app.route('/save_mission', methods=['POST'])
def save_mission():
    global coordinates
    data = request.get_json()
    file_name = data['file_name']
    print('Called save mission: ' + file_name + '.json')

    directory = 'missions/'

    # Check if directory exists
    if not os.path.exists(directory):
        os.makedirs(directory)  # If not, create it

    try:
        # Save to file
        with open(directory + file_name + '.json', 'w') as f:
            json.dump(coordinates, f)
        return 'Saved Mission: ' + file_name, 200
    except (IOError, OSError):
        return "Couldn't Save Mission: " + file_name, 400

@app.route('/load_mission', methods=['POST'])
def load_mission():
    global coordinates
    data = request.get_json()
    file_name = data['file_name']
    print('Called load mission: ' + file_name + '.json')

    directory = 'missions/'

    try:
        # Attempt to load from file
        with open(directory + file_name + '.json', 'r') as f:
            coordinates = json.load(f)

        log("Loaded Mission: " + file_name, 'success', 'MISSION')
        return jsonify({'message': f'Loaded Mission: {file_name}', 'coordinates': coordinates}), 200

    except FileNotFoundError:
        log("Couldn't Load Mission: " + file_name, 'error', 'MISSION')
        return jsonify({'error': 'Could not find file'}), 400

@socketio.on('connect')
def handle_connect():
    log("Client Connected", 'info', 'Socket')
    while not gps_queue.empty():
        lat, lng = gps_queue.get()
        socketio.emit('gps_data', {'lat': lat, 'lng': lng})
    while not imu_queue.empty():
        rotation = imu_queue.get()
        socketio.emit('imu_data', {'rotation': rotation})

@socketio.on('disconnect')
def handle_disconnect():
    log("Client Disconnected", 'info', 'Socket')

# Call this wherever you want to log something
def log(msg, level='info', prefix=None):
    socketio.emit('log', {'msg': msg, 'level': level, 'prefix': prefix})



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)