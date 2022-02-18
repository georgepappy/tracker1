import pandas as pd
import altair as alt
import geopandas as gpd
import json

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_wtf import FlaskForm 
from wtforms import SelectField, RadioField

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///covid.db'
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

db.Model.metadata.reflect(db.engine)


class state_data(db.Model):
    __table__ = db.Model.metadata.tables['state_data']

    def __repr__(self):
        return '%s %i %i %f %f %s ' % (self.Province_State, self.Confirmed, self.Deaths,
                            self.Incident_Rate, self.Case_Fatality_Ratio, self.Date)


class county_data(db.Model):
    __table__ = db.Model.metadata.tables['county_data']

    def __repr__(self):
        return '%s %s %i %i %f %f %s ' % (self.Admin2, self.Province_State,
                            self.Confirmed, self.Deaths, self.Incident_Rate, 
                            self.Case_Fatality_Ratio, self.Date)


states = ['','Alaska','Alabama','Arkansas','Arizona','California','Colorado','Connecticut','District of Columbia',
      'Delaware','Florida','Georgia','Hawaii','Iowa','Idaho','Illinois','Indiana','Kansas','Kentucky',
      'Louisiana','Massachusetts','Maryland','Maine','Michigan','Minnesota','Missouri','Mississippi',
      'Montana','North Carolina','North Dakota','Nebraska','New Hampshire','New Jersey','New Mexico',
      'Nevada','New York','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina',
      'South Dakota','Tennessee','Texas','Utah','Virginia','Vermont','Washington','Wisconsin',
      'West Virginia','Wyoming']

state_choices = [(n, val) for n, val in enumerate(states)]


class TableForm(FlaskForm):
    state = SelectField('state', 
                        choices=state_choices, 
                        default='California'
                       ) 
    county = SelectField('county', 
                         choices=[]
                        )

class MapForm(FlaskForm):
    since_start = RadioField('Reporting Window', 
                             choices = [('Since Pandemic Start', 'Since Pandemic Start'),
                                        ('Past 7 Days', 'Past 7 Days')]
                            ) 
    stat = RadioField('Reported Statistic', 
                      choices = [('Cases per 100k', 'Cases per 100k'),
                                 ('Total Deaths', 'Total Deaths'),
                                 ('Deaths per 100k', 'Deaths per 100k'),
                                 ('Death-to-Case Rate (%)', 'Death-to-Case Rate (%)')]
                     )

# Global variable holding latest values passed to html page
#   (Need this because there are 2 independent forms submitting to the same route, '/')
result = []

# Global variables holding map radio button settings on html page
#   (Need these so radio buttons remain consistent w/ map configuration when tables are updated)
since_start_string = 'Since Pandemic Start' # Initial default value
stat = 'Death-to-Case Rate (%)' # Initial default value


@app.route('/', methods=['GET', 'POST'])
def index():
    global result
    global since_start_string
    global stat
    table_form = TableForm()
    map_form = MapForm()

    # Set Choose County menu to default for No State Selected
    table_form.county.choices.append('(Choose State)')

    form_id = request.args.get('form_id', 1, type=int)


    ## POST 1: User submitting state and county selections for table display (form_id == 1)
    if (request.method == 'POST') and (form_id == 1):
        desired_state = state_choices[int(table_form.state.data)][1]

        counties = db.session.query(county_data.Admin2) \
                         .filter_by(Province_State=desired_state).distinct()
        counties_list = [(n, val[0]) for n, val in enumerate(counties)]
        if len(counties_list) == 0 or table_form.county.data == 'None Available':
            desired_county = 'None Available'
        else:
            desired_county = counties_list[int(table_form.county.data)][1] 

        county = db.session.query(county_data.Admin2) \
                   .filter_by(Province_State=desired_state) \
                   .filter_by(Admin2=desired_county).first()
        if county == None:
            county = 'None Available'
        else: 
            county = county[0]

        result_1 = state_data.query.filter_by(Province_State=desired_state) \
                                   .order_by(state_data.Date.desc()).first()

        if result_1 == None:
            results_1 = ['No State-Level Data Found']
            results_2 = ['No State-Level Data Found']
        else:
            result_2 = state_data.query.filter_by(Province_State=desired_state) \
                                       .order_by(state_data.Date.desc())[7]
            # Cumulative state-level results
            pop2021 = 100000 * result_1.Confirmed / result_1.Incident_Rate
            deaths_per_100k = 100000 * result_1.Deaths / pop2021
            results_1 = [result_1.Province_State,
                         '{:,}'.format(round(result_1.Incident_Rate, 1)),
                         '{:,}'.format(result_1.Deaths),
                         '{:,}'.format(round(deaths_per_100k, 1)),
                         '{:,}'.format(round(result_1.Case_Fatality_Ratio, 2))]

            # Compute the last-7-day data for state-level results
            confirmed_7_day = result_1.Confirmed - result_2.Confirmed
            deaths_7_day = result_1.Deaths - result_2.Deaths
            deaths_per_100k_7_day = 100000 * deaths_7_day / pop2021
            indicent_rate_7_day = 100000 * confirmed_7_day / pop2021
            if confirmed_7_day > 0:
                case_fatality_ratio_7_day = 100 * deaths_7_day / confirmed_7_day
            else:
                # Divide by zero case
                case_fatality_ratio_7_day = 0
            

            # Last-7-day state-level results
            results_2 = [result_1.Province_State,
                         '{:,}'.format(round(indicent_rate_7_day, 1)),
                         '{:,}'.format(deaths_7_day),
                         '{:,}'.format(round(deaths_per_100k_7_day, 1)),
                         '{:,}'.format(round(case_fatality_ratio_7_day, 2))]
        
        result_3 = county_data.query.filter_by(Province_State=desired_state) \
                                    .filter_by(Admin2=county) \
                                    .order_by(county_data.Date.desc()).first()

        if result_3 != None:
            result_4 = county_data.query.filter_by(Province_State=desired_state) \
                                        .filter_by(Admin2=county) \
                                        .order_by(county_data.Date.desc())[7]

        if result_3 == None:
            results_3 = ['No County-Level Data Found']
            results_4 = ['No County-Level Data Found']
        else:
            # Cumulative county-level results
            pop2021 = 100000 * result_3.Confirmed / result_3.Incident_Rate
            deaths_per_100k = 100000 * result_3.Deaths / pop2021
            results_3 = [result_3.Admin2,
                         result_3.Province_State,
                         '{:,}'.format(round(result_3.Incident_Rate, 1)),
                         '{:,}'.format(result_3.Deaths),
                         '{:,}'.format(round(deaths_per_100k, 1)),
                         '{:,}'.format(round(result_3.Case_Fatality_Ratio, 2))]

            # Compute the last-7-day data for county-level results
            confirmed_7_day = result_3.Confirmed - result_4.Confirmed
            deaths_7_day = result_3.Deaths - result_4.Deaths
            deaths_per_100k_7_day = 100000 * deaths_7_day / pop2021
            indicent_rate_7_day = 100000 * confirmed_7_day / pop2021
            if confirmed_7_day > 0:
                case_fatality_ratio_7_day = 100 * deaths_7_day / confirmed_7_day
            else:
                # Divide by zero case
                case_fatality_ratio_7_day = 0

            # Last-7-day county-level results
            results_4 = [result_3.Admin2,
                         result_3.Province_State,
                         '{:,}'.format(round(indicent_rate_7_day, 1)),
                         '{:,}'.format(deaths_7_day),
                         '{:,}'.format(round(deaths_per_100k_7_day, 1)),
                         '{:,}'.format(round(case_fatality_ratio_7_day, 2))]

        if len(result) == 5:
            # Retrieve user's previously-selected choroplth map configuration
            map_data = result[4]
        else:
            # Make & get default choropleth map (no user selected map cofig yet)
            gen_map(since_start=True, stat='Death-to-Case Rate (%)')
            with open('map_chart.json') as f:
                map_data = json.dumps(json.load(f))

        result = [results_1, results_2, results_3, results_4, map_data]

        # Update radio button defaults to remain consistent with current map configuration
        map_form.since_start.data = since_start_string
        map_form.stat.data = stat

        # Set Choose State Menu back to blank
        table_form.state.data = '0'

        return render_template("index.html", form = [table_form, map_form], result=result)

    ## POST 2: User submitting radio button selections for map display (i.e. form_id == 2)
    if (request.method == 'POST') and (form_id == 2):

        # Retain the existing state and county data
        result = result[0:4]

        # Get the new requested choropleth map
        since_start_string = map_form.since_start.data
        since_start = True if since_start_string == 'Since Pandemic Start' else False
        stat = map_form.stat.data
        gen_map(since_start=since_start, stat=stat)
        with open('map_chart.json') as f:
            map_data = json.dumps(json.load(f))

        result.append(map_data)

        return render_template("index.html", form = [table_form, map_form], result=result)

    return render_template('index.html', form=[table_form, map_form])      



@app.route('/county/<state>')
def county(state):
    desired_state = state_choices[int(state)][1]
    counties = db.session.query(county_data.Admin2) \
                         .filter_by(Province_State=desired_state).distinct()

    counties_list = [(n, val[0]) for n, val in enumerate(counties)]
    if len(counties_list) == 0:
        counties_list.append('None Available')

    countyArray = []
    for county in counties_list:
        countyObj = {}
        if county != 'None Available':
            countyObj['id'] = county[0]
            countyObj['name'] = county[1]
        else:
            countyObj['id'] = '0'
            countyObj['name'] = county
        countyArray.append(countyObj)

    return jsonify({'counties' : countyArray})



@app.after_request
def add_header(r):
    r.headers["Cache-Control"]  = "no-store max-age=0"
    return r



def gen_map(since_start=False, stat='Deaths per 100k'):
    """
        since_start (boolean) : True for 'Since Pandemic Start'
                                False for 'Past 7 Days'
        stat (string) : One of ['Cases per 100k', 'Total Deaths', 
                                'Deaths per 100k', 'Death-to-Case Rate (%)']
    """
    
    # Query "today's" data
    result_1 = state_data.query.order_by(state_data.Date.desc())[0:51]
    if not since_start:
        # Query '7 days ago' data
        result_2 = state_data.query.order_by(state_data.Date.desc())[357:408]
    else:
        # Only doing this to facilitate the zip used below
        result_2 = result_1

    results = []
    for row_1, row_2 in zip(result_1, result_2):
        pop2021 = 100000 * row_1.Confirmed / row_1.Incident_Rate
        if since_start:
            deaths_per_100k = 100000 * row_1.Deaths / pop2021
            results.append((row_1.Province_State,
                            deaths_per_100k,
                            row_1.Deaths,
                            row_1.Incident_Rate,
                            row_1.Case_Fatality_Ratio,
                            pop2021))
        else:
            # Compute the last-7-day data for state-level results
            confirmed_7_day = row_1.Confirmed - row_2.Confirmed
            deaths_7_day = row_1.Deaths - row_2.Deaths
            deaths_per_100k_7_day = 100000 * deaths_7_day / pop2021,
            incident_rate_7_day = 100000 * confirmed_7_day / pop2021
            if confirmed_7_day > 0:
                case_fatality_ratio_7_day = 100 * deaths_7_day / confirmed_7_day
            else:
                # Divide by zero case
                case_fatality_ratio_7_day = 0
            results.append((row_1.Province_State,
                            deaths_per_100k_7_day,
                            deaths_7_day,
                            incident_rate_7_day,
                            case_fatality_ratio_7_day,
                            pop2021))

    df = pd.DataFrame(results,
                      columns=['Province_State', 'Deaths_per_100k', 'Deaths', 
                               'Incident_Rate', 'Case_Fatality_Ratio', 'pop2021']
                     )

    with open('gz_2010_us_040_00_20m.json') as json_data:
        gdf = gpd.GeoDataFrame.from_features(json.load(json_data))


    gdf = gdf.merge(df, how='inner', left_on='NAME', right_on='Province_State') \
             .drop(columns=['Province_State'])

    choro_json = json.loads(gdf.to_json())
    
    choro_data = alt.Data(values=choro_json['features'])

    scale = alt.Scale(scheme='blues')

    if stat == 'Deaths per 100k':
        color = alt.Color('properties.Deaths_per_100k:Q', title='Deaths per 100k', scale=scale)
    elif stat == 'Total Deaths': 
        color = alt.Color('properties.Deaths:Q', title='Total Deaths', scale=scale)
    elif stat == 'Cases per 100k':
        color = alt.Color('properties.Incident_Rate:Q', title='Cases per 100k', scale=scale)
    else:
        color = alt.Color('properties.Case_Fatality_Ratio:Q', title='Death-to-Case Rate (%)', scale=scale)

    tooltip = [alt.Tooltip('properties.NAME:O', title='State'),
               alt.Tooltip('properties.pop2021:Q', format=",.0f", title='Population'),
               alt.Tooltip('properties.Incident_Rate:Q', format=",.1f", title='Cases per 100k'),
               alt.Tooltip('properties.Deaths:Q', format=",.0f", title='Total Deaths'),
               alt.Tooltip('properties.Deaths_per_100k:Q', format=",.1f", title='Deaths per 100k'),
               alt.Tooltip('properties.Case_Fatality_Ratio:Q', format=",.2f", title='Death-to-Case Rate (%)')]

    if since_start:
        title = stat + ' by State' + ' (Since Pandemic Start)'    
    else:
        title = stat + ' by State' + ' (Past 7 Days)'

    map_chart = (alt.Chart(data=choro_data).mark_geoshape(stroke='black')
                    .encode(
                        color=color,
                        tooltip=tooltip)
                    .project(
                        type='albersUsa'
                    )
                    .properties(
                        title=title,
                        width=750,
                        height=450
                    ).configure_legend(
                        orient='right',
                        direction='vertical',
                        padding = 10,
                        offset = 50,
                        gradientLength=400,
                        gradientThickness=40,
                        titleFontSize=14,
                        titleAlign='center',
                        titlePadding=10,
                        labelFontSize=14,
                        labelFontWeight='bold'
                    ).configure_view(
                        strokeWidth=0
                    ).configure_title(
                        fontSize=20,
                        fontWeight='bold',
                        anchor="middle"
                    )
                )

    map_chart.save('map_chart.json')

    return None



if __name__ == '__main__':
    app.run(debug=True)