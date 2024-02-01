import asyncio
from env_canada import ECWeather
from flask import Flask, render_template, request
import requests
import matplotlib.pyplot as plt
import mpld3
import numpy as np


app = Flask(__name__)

api_key_googlemaps = "AIzaSyDFUnNyNUx2PYV9tRyrZ54opZCJ3CHjInI"
country_code = "CA"

def get_coordinates(api_key, location):
    try:
        address = f"{location}, {country_code}"
        geocoding_url = f'https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}'
        response = requests.get(geocoding_url)
        data = response.json()

        if data.get('status') == 'OK' and data.get('results'):
            location = data['results'][0]['geometry']['location']
            return {'lat': location['lat'], 'lng': location['lng']}

    except Exception as e:
        print(f'Error fetching coordinates for {address}: {str(e)}')

    return None

def get_temperature(location, controlled):
    if controlled:
        return None
    else:
        coordinates = get_coordinates(api_key_googlemaps, location)

        if coordinates:
            ec_weather = ECWeather(coordinates=(coordinates['lat'], coordinates['lng']))
            asyncio.run(ec_weather.update())
            temperature = ec_weather.conditions['temperature']['value']
            return temperature
        else:
            return None

def handle_uncontrolled_temperature(at_depot, min_temp, max_temp, current_temp):
    if at_depot:
        if current_temp < min_temp:
            return min_temp
        elif min_temp <= current_temp <= max_temp:
            return current_temp
        else:
            return max_temp
    else:
        return current_temp

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        steps = []
        source_location = request.form['sourceLocation']
        source_temperature = request.form['sourceTemperature']
        source_duration = float(request.form['sourceDuration'])

        source_api_temperature = get_temperature(source_location, False)

        step_index = 1
        cumulative_duration = source_duration

        while f'stepLocation{step_index}' in request.form:
            step_location = request.form[f'stepLocation{step_index}']
            step_duration = float(request.form[f'stepDuration{step_index}'])
            at_carrier_depot = 'atCarrierDepot' + str(step_index) in request.form
            in_transit = 'inTransit' + str(step_index) in request.form
            controllable = 'controllable' + str(step_index) in request.form
            step_temperature = request.form.get(f'stepTemperature{step_index}', '')

            if not step_temperature:
                step_temperature = get_temperature(step_location, controllable)
                min_temp_str = request.form.get(f'MinTemp{step_index}', '')
                min_temp = float(min_temp_str) if min_temp_str else 0.0
                max_temp_str = request.form.get(f'MaxTemp{step_index}', '')
                max_temp = float(max_temp_str) if max_temp_str else 0.0
                step_temperature = handle_uncontrolled_temperature(at_carrier_depot, min_temp, max_temp, step_temperature)

            status = 'In Transit' if in_transit else 'At Depot'
            steps.append({
                'location': step_location,
                'duration': step_duration,
                'status': status,
                'controllable': controllable,
                'temperature': step_temperature,
            })
            step_index += 1

        x_values = [0]
        y_values = [float(source_temperature)]

        cumulative_duration = source_duration
        for step in steps:
            x_values.extend([cumulative_duration, cumulative_duration + step['duration']])
            y_values.extend([float(step['temperature']), float(step['temperature'])])
            cumulative_duration += step['duration']

        fig, ax = plt.subplots()

        ax.step(x_values, y_values, where='post', color='blue', label='Temperature')

        sorted_y_ticks = sorted(set(y_values))
        ax.set_yticks(sorted_y_ticks)

        ax.set_xlabel('Duration')
        ax.set_ylabel('Temperature')
        ax.set_title('Temperature vs Duration')
        ax.legend()
        ax.grid(True)

        plt.savefig('static/temperature_graph.png') 
        plt.close()  

        return render_template('result_table.html', source_location=source_location,
                               source_temperature=source_temperature, source_duration=source_duration,
                               source_api_temperature=source_api_temperature, steps=steps,
                               graph_image='temperature_graph.png')  

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
