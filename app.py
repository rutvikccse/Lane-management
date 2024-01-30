import asyncio
from env_canada import ECWeather
from flask import Flask, render_template, request
import requests

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
        source_duration = request.form['sourceDuration']


        source_api_temperature = get_temperature(source_location, False)

        step_index = 1
        while f'stepLocation{step_index}' in request.form:
            step_location = request.form[f'stepLocation{step_index}']
            step_duration = request.form[f'stepDuration{step_index}']
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


            steps.append({
                'location': step_location,
                'duration': step_duration,
                'at_carrier_depot': at_carrier_depot,
                'in_transit': in_transit,
                'controllable': controllable,
                'temperature': step_temperature,
            })

            step_index += 1

        print("Source Location:", source_location)
        print("Source Temperature:", source_temperature)
        print("Source Duration:", source_duration)
        print("Temperature obtained from API for Source:", source_api_temperature)

        print("Temperatures and Durations for each step:")

        for step_index, step in enumerate(steps, start=1):
            location = step['location']
            duration = step['duration']
            controllable_checkbox_name = 'controllable' + str(step_index)

            controlled = controllable_checkbox_name in request.form

            if 'inTransit' + str(step_index) in request.form:
                if controlled:
                    temperature = request.form.get(f'stepTemperature{step_index}', '')
                    print(f"Step {step_index} - In Transit, Controlled Temperature: {temperature}, Duration: {duration}")
                else:
                    temperature = get_temperature(location, controlled)
                    print(f"Step {step_index} - In Transit, Non-Controlled Temperature: {temperature}, Duration: {duration}")

            elif 'atCarrierDepot' + str(step_index) in request.form:
                if controlled:
                    temperature = request.form.get(f'stepTemperature{step_index}', '')
                    print(f"Step {step_index} - At Depot, Controlled Temperature: {temperature}, Duration: {duration}")
                else:
                    temperature = get_temperature(location, controlled)
                    print(f"Step {step_index} - At Depot, Non-Controlled Temperature: {temperature}, Duration: {duration}")

            else:
                if controlled:
                    temperature = request.form.get(f'stepTemperature{step_index}', '')
                    print(f"Step {step_index} - Controlled Temperature: {temperature}, Duration: {duration}")
                else:
                    temperature = get_temperature(location, controlled)
                    print(f"Step {step_index} - Non-Controlled Temperature: {temperature}, Duration: {duration}")
            
        return render_template('result_table.html', source_location=source_location, 
                               source_temperature=source_temperature, source_duration=source_duration,
                               source_api_temperature=source_api_temperature, steps=steps)

    return render_template('index.html')
    
if __name__ == '__main__':
    app.run(debug=True)
