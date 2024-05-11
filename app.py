from flask import Flask, jsonify, make_response
from flask_restful import Resource, Api, reqparse
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO
import psycopg2
import psycopg2.extras
import string
import random
import traceback
from re import match
import paho.mqtt.client as mqtt
import json  
import os


#client.loop_forever()

app = Flask(__name__)
SocketIO(app)
api = Api(app)
CORS(app, resources={r'/*': {'origins': '*'}})

def createSerialNumber():
    range1 = string.ascii_lowercase[:26]
    range2 = string.ascii_uppercase[:26]
    range3 = string.digits[:10]
    SerialNumber = ""
    NumberRange = list(range1 + range2 + range3)
    while(len(SerialNumber) < 16):
        ChoiceNum = random.choice(NumberRange)
        SerialNumber += ChoiceNum
    return SerialNumber

def conndb():
    db = psycopg2.connect(database="coffeeDB", user="postgres", 
                          password="changeme", host="172.233.72.40", 
                          port="5432")
    return db
    
    

class MachineInit(Resource):
    def get(self):
        db = conndb()
        cursor = db.cursor()

        response = {}

        while True:
            SerialNumber = createSerialNumber()
            sql = """
            SELECT COUNT(machine_id) FROM machineregister WHERE machine_id = '{}'
              """.format(SerialNumber)
            
            try:
                cursor.execute(sql)
            except:
                traceback.print_exc()

            req = cursor.fetchone()

            if(req[0] == 0):
                response['SerialNumber'] = SerialNumber
                break

        return jsonify(response) 

class MachineRegister(Resource):
    def post(self):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('machine_id')
        parser.add_argument('machine_name')
        parser.add_argument('temperature')
        parser.add_argument('machine_state')
        arg = parser.parse_args()
        Machine = {
            'machine_id' : arg['machine_id'],
            'machine_name' : arg['machine_name'],
            'temperature' : arg['temperature'],
            'machine_state' : arg['machine_state'],
        }
        
        sql = """
            INSERT INTO machineregister (machine_id, machine_name, temperature, machine_state) VALUES ('{}', '{}', '{}', '{}')
              """.format(Machine['machine_id'], Machine['machine_name'], Machine['temperature'], Machine['machine_state'])
        

        response = {}
        
        try:
            cursor.execute(sql)
            response['msg'] = '登記成功'
        except:
            traceback.print_exc()
            response['msg'] = '登記失敗'

        db.commit()
        db.close()

        return jsonify(response)

class SelectMchine(Resource):
    def get(self, select_id):
        db = conndb()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = """
            SELECT * FROM 
            (SELECT machineregister.machine_id, machine_name, machine_state, temperature, user_id FROM machineuser
            LEFT JOIN machineregister
            ON machineuser.machine_id = machineregister.machine_id)
            WHERE machine_id = '{}'
              """.format(select_id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = "查詢成功"
            response['machine'] = cursor.fetchone()
        except:
            traceback.print_exc()

        db.close()

        return response

class MachineSelect(Resource):
    @cross_origin()
    def get(self, user_id):
        db = conndb()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = """
            SELECT * FROM 
            (SELECT * FROM machineuser
            LEFT JOIN machineregister
            ON machineuser.machine_id = machineregister.machine_id)
            WHERE user_id = '{}'
              """.format(user_id)
        
        try:
            cursor.execute(sql)
            machines = cursor.fetchall()
        except:
            traceback.print_exc()


        db.commit()
        db.close()
        return jsonify({'machines' : machines})
    

class MachineUpdate(Resource):
    def put(self, machine_id):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('machine_name')
        parser.add_argument('temperature')
        parser.add_argument('machine_state')
        arg = parser.parse_args()
        Machine = {
            'machine_name' : arg['machine_name'],
            'temperature' : arg['temperature'],
            'machine_state' : arg['machine_state'],
        }
        sql = """
            UPDATE machineregister SET machine_name = '{}', temperature = '{}', machine_state = '{}' WHERE machine_id = '{}'
              """.format(Machine['machine_name'], Machine['temperature'], Machine['machine_state'], machine_id)
        
        response = {}
        
        try:
            cursor.execute(sql)
            response['msg'] = '修改成功'
        except:
            traceback.print_exc()
            response['msg'] = '修改失敗'

        db.commit()
        db.close()
        return jsonify(response)

class MachineUser(Resource):
    def post(self):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('machine_id')
        parser.add_argument('user_id')
        arg = parser.parse_args()
        MachineUser = {
            'machine_id' : arg['machine_id'],
            'user_id' : arg['user_id'],
        }

        selectsql = """
                    SELECT COUNT(*) FROM machineuser WHERE machine_id = '{}' AND user_id = '{}'
                    """.format(MachineUser['machine_id'], MachineUser['user_id'])
        

        sql = """
            INSERT INTO machineuser (machine_id, user_id) VALUES ('{}', '{}')
              """.format(MachineUser['machine_id'], MachineUser['user_id'])

        response = {}

        try:
            cursor.execute(selectsql)
            req = cursor.fetchone()
            if(req[0] != 0):
                response['msg'] = '重複新增'
                return jsonify(response)    
        except:
            traceback.print_exc()
        
        try:
            cursor.execute(sql)
            response['msg'] = '新增成功'
            response['machineuser'] = MachineUser
        except:
            traceback.print_exc()
            response['msg'] = '新增失敗'

        db.commit()
        db.close()

        return jsonify(response)
    
    def delete(self, id):
        db = conndb()
        cursor = db.cursor()
        result = {}
        parser = reqparse.RequestParser()
        if(match(r'[A-Za-z0-9]{16}',id)):
            parser.add_argument('machineuser')
            arg = parser.parse_args()
            result['machine_id'] = id
            result['user_id'] = arg['machineuser']
        elif(match(r'U[0-9a-f]{32}',id)):
            parser.add_argument('machineuser')
            arg = parser.parse_args()
            result['machine_id'] = arg['machineuser']
            result['user_id'] = id

        sql = """
            DELETE FROM machineuser WHERE machine_id = '{}' AND user_id = '{}';
              """.format(result['machine_id'], result['user_id'])
        
        response = {}
        response['id'] = id
        response['machineuser'] = arg['machineuser']
        response['result'] = result
        response['sql'] = sql
        try:
            cursor.execute(sql)
            response['msg'] = '刪除成功'
        except:
            traceback.print_exc()
            response['msg'] = '刪除失敗'

        db.commit()
        db.close()

        return jsonify(response)

class Components(Resource):
    def get(self, components_id):
        db = conndb()
        cursor = db.cursor()

        sql = """
            SELECT * FROM WHERE machine_id = '{}'
              """.format(components_id)
        response = {}

        try:
            cursor.execute(sql)
            response = cursor.fetchall()
        except:
            traceback.print_exc()
            response['msg'] = '查詢失敗'

        db.commit()
        db.close()

        return jsonify(response)

    def post(self):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('component_id')
        parser.add_argument('machine_id')
        parser.add_argument('component_type')
        parser.add_argument('component_state')
        arg = parser.parse_args()
        component = {
            'component_id' : arg['component_id'],
            'machine_id' : arg['machine_id'],
            'component_type' : arg['component_type'],
            'component_state' : arg['component_state'],
        }

        selectsql = """
                    SELECT COUNT(*) FROM components WHERE component_id = '{}' AND machine_id = '{}'
                    """.format(component['component_id'], component['machine_id'])
        
        sql = """
            INSERT INTO components (component_id, machine_id, component_type, component_state) VALUES ('{}', '{}', '{}', '{}')
              """.format(component['component_id'], component['machine_id'], component['component_type'], component['component_state'])
        
        response = {}

        try:
            cursor.execute(selectsql)
            req = cursor.fetchone()
            if(req[0] != 0):
                response['msg'] = '重複新增'
                return jsonify(response)    
        except:
            traceback.print_exc()
        
        try:
            cursor.execute(sql)
            response['msg'] = '新增成功'
        except:
            traceback.print_exc()
            response['msg'] = '新增失敗'

        db.commit()
        db.close()

        return jsonify(response)
    
    def delete(self, components_id):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('id')
        arg = parser.parse_args()

        sql = """
            DELETE FROM components WHERE (component_id = '{}' AND machine_id = '{}') OR (component_id = '{}' AND machine_id = '{}');
              """.format(components_id, arg['id'], arg['id'], components_id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '刪除成功'
        except:
            traceback.print_exc()
            response['msg'] = '刪除失敗'

        db.commit()
        db.close()

        return jsonify(response)

class BrewLog(Resource):
    def post(self):
        def on_connect(client, userdata, flags, rc):
            print("Connected with result code "+str(rc))
            client.subscribe("class")
        def on_message(client, userdata, msg):
            print(msg.topic+" "+ msg.payload.decode('utf-8'))
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect("54.mqttbroker.srchen.cc", 1883, 60)
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('brew_timestamp')
        parser.add_argument('brew_date')
        parser.add_argument('capsule_type')
        parser.add_argument('user_id')
        parser.add_argument('machine_id')
        parser.add_argument('Water_volume')
        parser.add_argument('temperature')
        parser.add_argument('air_pressure')
        arg = parser.parse_args()
        brewlog = {
            'brew_timestamp' : arg['brew_timestamp'],
            'brew_date' : arg['brew_date'], 
            'capsule_type' : arg['capsule_type'],
            'user_id' : arg['user_id'],
            'machine_id' : arg['machine_id'],
            'Water_volume' : arg['Water_volume'],
            'temperature' : arg['temperature'],
            'air_pressure' : arg['air_pressure'],
        }
        mqttmessage = {
            'action' : 'brew',
            'brew_timestamp' : arg['brew_timestamp'],
            'brew_date' : arg['brew_date'], 
            'capsule_type' : arg['capsule_type'],
            'user_id' : arg['user_id'],
            'machine_id' : arg['machine_id'],
            'Water_volume' : arg['Water_volume'],
            'temperature' : arg['temperature'],
            'air_pressure' : arg['air_pressure'],
        }
        client.publish("class", json.dumps(mqttmessage))
        sql = """
            INSERT INTO brew_log (brew_timestamp, brew_date, capsule_type, user_id, machine_id, Water_volume, temperature, air_pressure) VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')
              """.format(brewlog['brew_timestamp'], brewlog['brew_date'], brewlog['capsule_type'], brewlog['user_id'], brewlog['machine_id'], brewlog['Water_volume'], brewlog['temperature'], brewlog['air_pressure'])
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '新增成功'
        except:
            traceback.print_exc()
            response['msg'] = '新增失敗'

        db.commit()
        db.close()

        return jsonify(response)
    
    def get(self, brew_user):
        db = conndb()
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        sql = """
            SELECT brew_date as date, capsule_type as type, machine_name as machine
            FROM (
                SELECT * FROM brew_log right join machineregister ON brew_log.machine_id = machineregister.machine_id
            ) WHERE user_id = '{}'
              """.format(brew_user)
        

        try:
            cursor.execute(sql)
            brew_log = cursor.fetchall()
        except:
            traceback.print_exc()

        db.commit()
        db.close()

        return jsonify({'brew_log' : brew_log})

class Temperature(Resource):
    def get(self, id):
        db = conndb()
        cursor = db.cursor()
        
        sql = """
            SELECT temperature FROM machineregister WHERE machine_id = '{}'
              """.format(id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '查詢成功'
            response['temperature'] = cursor.fetchone()[0]
        except:
            traceback.print_exc()
            response['msg'] = '查詢失敗'
        
        db.commit()
        db.close()

        return jsonify(response)

    def put(self, id):
        def on_connect(client, userdata, flags, rc):
            print("Connected with result code "+str(rc))
            client.subscribe("class")
        def on_message(client, userdata, msg):
            print(msg.topic+" "+ msg.payload.decode('utf-8'))
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect("54.mqttbroker.srchen.cc", 1883, 60)
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('temperature')
        arg = parser.parse_args()
        temperature = {
            'temperature' : arg['temperature']
        }
        mqttmessage = {
            'action' : 'set_temperature',
            'machine_id' : id,
            'temperature' : arg['temperature']
        }
        client.publish("class", json.dumps(mqttmessage))
        sql = """
            UPDATE machineregister SET temperature = '{}' WHERE machine_id = '{}'
              """.format(temperature['temperature'], id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '修改成功'
            response['temperature'] = temperature
        except:
            traceback.print_exc()
            response['msg'] = '修改失敗'
        
        db.commit()
        db.close()

        return jsonify(response)

class RealTemperature(Resource):
    def get(self, id):
        db = conndb()
        cursor = db.cursor()
        
        sql = """
            SELECT now_temperature FROM machineregister WHERE machine_id = '{}'
              """.format(id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '查詢成功'
            response['now_temperature'] = cursor.fetchone()[0]
        except:
            traceback.print_exc()
            response['msg'] = '查詢失敗'
        
        db.commit()
        db.close()

        return jsonify(response)
    
    def put(self, id):
        db = conndb()
        cursor = db.cursor()
        parser = reqparse.RequestParser()
        parser.add_argument('now_temperature')
        arg = parser.parse_args()
        temperature = {
            'now_temperature' : arg['now_temperature']
        }
        sql = """
            UPDATE machineregister SET now_temperature = '{}' WHERE machine_id = '{}'
              """.format(temperature['now_temperature'], id)
        
        response = {}

        try:
            cursor.execute(sql)
            response['msg'] = '修改成功'
            response['now_temperature'] = temperature
        except:
            traceback.print_exc()
            response['msg'] = '修改失敗'
        
        db.commit()
        db.close()

        return jsonify(response)

api.add_resource(MachineInit, '/api/MachineInit')
api.add_resource(MachineRegister, '/api/MachineRegister')
api.add_resource(SelectMchine, '/api/SelectMchine/<string:select_id>', endpoint='/<string:select_id>')
api.add_resource(MachineSelect, '/api/MachineSelect/<string:user_id>', endpoint='/string:user_id')
api.add_resource(MachineUpdate, '/api/MachineUpdate/<string:machine_id>')
api.add_resource(MachineUser, '/api/MachineUser', endpoint='MachineUser')
api.add_resource(MachineUser, '/api/MachineUser/<string:id>', endpoint='/<string:id>')
api.add_resource(Components, '/api/Components', endpoint='Components')
api.add_resource(Components, '/api/Components/<string:components_id>', endpoint='/<string:components_id>')
api.add_resource(BrewLog, '/api/BrewLog')
api.add_resource(BrewLog, '/api/BrewLog/<string:brew_user>', endpoint='/<string:brew_user>')
api.add_resource(Temperature, '/api/Temperature/<string:id>')
api.add_resource(RealTemperature, '/api/RealTemperature/<string:id>')







if __name__ == '__main__':
    app.debug = True
    app.run(port=os.getenv("PORT", default=5000), host='0.0.0.0')