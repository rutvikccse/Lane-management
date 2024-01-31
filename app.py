import asyncio
from env_canada import ECWeather
from flask import Flask, render_template, request
import requests
import matplotlib.pyplot as plt
import mpld3

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
        graph_data = [{'duration': 0, 'temperature': float(source_temperature), 'status': 'Source'}]
        graph_data.append({'duration': source_duration, 'temperature': float(source_temperature)})

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
            cumulative_duration += step_duration

            graph_data.append({'duration': cumulative_duration, 'temperature': float(step_temperature), 'status': status})
            print(graph_data)
            step_index += 1
            
        durations = [data['duration'] for data in graph_data]
        temperatures = [data['temperature'] for data in graph_data]

        fig, ax = plt.subplots()
        ax.step(durations, temperatures, where='post', marker='o')
        ax.set_title('Temperature vs Cumulative Duration (Step Graph)')
        ax.set_xlabel('Cumulative Duration (hours)')
        ax.set_ylabel('Temperature (°C)')
        plt.grid(True, alpha=0.3)

        graph_html = mpld3.fig_to_html(fig)

        return render_template('result_table.html', source_location=source_location,
                               source_temperature=source_temperature, source_duration=source_duration,
                               source_api_temperature=source_api_temperature, steps=steps, graph_html=graph_html)

    return render_template('index.html')




if __name__ == '__main__':
    app.run(debug=True)
