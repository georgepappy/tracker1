from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_wtf import FlaskForm 
from wtforms import SelectField

app = Flask(__name__)

# app.config['SECRET_KEY'] = 'secret'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../covid.db'
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

db.Model.metadata.reflect(db.engine)


class state_data(db.Model):
    __table__ = db.Model.metadata.tables['state_data']

    def __repr__(self):
        return '%s %f %f %i %i %f %f %i %s ' % (self.Province_State, self.Lat, self.Long_, 
                            self.Confirmed, self.Deaths, 
                            self.Incident_Rate, self.Case_Fatality_Ratio, 
                            self.pop2021, self.Date)

class county_data(db.Model):
    __table__ = db.Model.metadata.tables['county_data']

    def __repr__(self):
        return '%s %s %f %f %i %i %i %f %f %s ' % (self.Admin2, self.Province_State, 
                            self.Lat, self.Long_, self.Confirmed, self.Deaths, 
                            self.pop2021, self.Incident_Rate, 
                            self.Case_Fatality_Ratio, self.Date)


states = ['Alaska','Alabama','Arkansas','Arizona','California','Colorado','Connecticut','District of Columbia',
      'Delaware','Florida','Georgia','Hawaii','Iowa','Idaho','Illinois','Indiana','Kansas','Kentucky',
      'Louisiana','Massachusetts','Maryland','Maine','Michigan','Minnesota','Missouri','Mississippi',
      'Montana','North Carolina','North Dakota','Nebraska','New Hampshire','New Jersey','New Mexico',
      'Nevada','New York','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina',
      'South Dakota','Tennessee','Texas','Utah','Virginia','Vermont','Washington','Wisconsin',
      'West Virginia','Wyoming']

state_choices = [(n, val) for n, val in enumerate(states)]


class Form(FlaskForm):
    state = SelectField('state', choices=state_choices) 
    county = SelectField('county', choices=[])


@app.route('/', methods=['GET', 'POST'])
def index():
    form = Form()
    county_query = db.session.query(county_data.Admin2) \
                             .filter_by(Province_State='Alaska').distinct()
    form.county.choices = [(n, val[0]) for n, val in enumerate(county_query)]
    if len(form.county.choices) == 0:
        form.county.choices.append('None Available')

    if request.method == 'POST':
        desired_state = state_choices[int(form.state.data)][1]

        counties = db.session.query(county_data.Admin2) \
                         .filter_by(Province_State=desired_state).distinct()
        counties_list = [(n, val[0]) for n, val in enumerate(counties)]
        if len(counties_list) == 0 or form.county.data == 'None Available':
            desired_county = 'None Available'
        else:
            desired_county = counties_list[int(form.county.data)][1] 

        county = db.session.query(county_data.Admin2) \
                   .filter_by(Province_State=desired_state) \
                   .filter_by(Admin2=desired_county).first()
        if county == None:
            county = 'None Available'
        else: 
            county = county[0]

        result_1 = state_data.query.filter_by(Province_State=desired_state) \
                                   .order_by(state_data.Date.desc()).first()

        if result_1 != None:
            result_2 = state_data.query.filter_by(Province_State=desired_state) \
                                       .order_by(state_data.Date.desc())[7]

        if result_1 == None:
            results_1 = ['No County-Level Results Available']
            results_2 = ['No County-Level Results Available']
        else:
            # Cumulative state-level results
            results_1 = [result_1.Province_State,
                         '{:,}'.format(result_1.Confirmed),
                         '{:,}'.format(result_1.Deaths),
                         '{:,}'.format(round(result_1.Incident_Rate, 1)),
                         '{:,}'.format(round(result_1.Case_Fatality_Ratio, 2))]

            # Compute the last-7-day data for state-level results
            confirmed_7_day = result_1.Confirmed - result_2.Confirmed
            deaths_7_day = result_1.Deaths - result_2.Deaths
            indicent_rate_7_day = 100000 * confirmed_7_day / result_1.pop2021
            case_fatality_ratio_7_day = 100 * deaths_7_day / confirmed_7_day

            # Last-7-day state-level results
            results_2 = [result_1.Province_State,
                         '{:,}'.format(confirmed_7_day),
                         '{:,}'.format(deaths_7_day),
                         '{:,}'.format(round(indicent_rate_7_day, 1)),
                         '{:,}'.format(round(case_fatality_ratio_7_day, 2))]
        
        result_3 = county_data.query.filter_by(Province_State=desired_state) \
                                    .filter_by(Admin2=county) \
                                    .order_by(county_data.Date.desc()).first()

        if result_3 != None:
            result_4 = county_data.query.filter_by(Province_State=desired_state) \
                                        .filter_by(Admin2=county) \
                                        .order_by(county_data.Date.desc())[7]

        if result_3 == None:
            results_3 = ['No County-Level Results Available']
            results_4 = ['No County-Level Results Available']
        else:
            # Cumulative county-level results
            results_3 = [result_3.Admin2,
                         result_3.Province_State,
                         '{:,}'.format(result_3.Confirmed),
                         '{:,}'.format(result_3.Deaths),
                         '{:,}'.format(round(result_3.Incident_Rate, 1)),
                         '{:,}'.format(round(result_3.Case_Fatality_Ratio, 2))]

            # Compute the last-7-day data for county-level results
            confirmed_7_day = result_3.Confirmed - result_4.Confirmed
            deaths_7_day = result_3.Deaths - result_4.Deaths
            indicent_rate_7_day = 100000 * confirmed_7_day / result_3.pop2021
            case_fatality_ratio_7_day = 100 * deaths_7_day / confirmed_7_day

            # Last-7-day county-level results
            results_4 = [result_3.Admin2,
                         result_3.Province_State,
                         '{:,}'.format(confirmed_7_day),
                         '{:,}'.format(deaths_7_day),
                         '{:,}'.format(round(indicent_rate_7_day, 1)),
                         '{:,}'.format(round(case_fatality_ratio_7_day, 2))]

        return render_template("index.html", form = form, 
                               result=[results_1, results_2, results_3, results_4])

    return render_template('index.html', form=form)      


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


if __name__ == '__main__':
    app.run(debug=True)