from flask import Flask, render_template, request
import folium
import pandas as pd
import os

app = Flask(__name__, static_url_path='/static', static_folder='static')
coordinates = []

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
    return 'Saved Mission: ' + file_name, 200

@app.route('/load_mission', methods=['POST'])
def load_mission():
    global coordinates
    data = request.get_json()
    file_name = data['file_name']
    print('Called load mission: ' + file_name + '.json')
    return 'Loaded Mission: ' + file_name, 200

if __name__ == '__main__':
    app.run(debug=True)