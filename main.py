from flask import Flask, jsonify, request, render_template, make_response
from DAL import DataBase
from random import shuffle
from datetime import datetime

def decode_unicode(data):
    if isinstance(data, str):
        return data.encode().decode('utf-8')
    elif isinstance(data, dict):
        return {key: decode_unicode(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [decode_unicode(item) for item in data]
    return data

dal = DataBase("config_bot_tinder.ini")
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

@app.route("/")
def index():
    return render_template("index.html")

# Create a new user
@app.route("/users", methods=["POST"])
def create_user():
    data = request.json
    telegram_id = data.get("telegram_id")
    name = data.get("name")
    age = data.get("age")
    sex = data.get("sex")
    interested_in = data.get("interested_in")
    about_me = data.get("about_me")
    if telegram_id and name and age and sex and interested_in:
        # Insert the new user into the database
        dal.execute_query("INSERT INTO User (telegram_id, Name, Age, Sex, Interested_in, About_me) VALUES (%s, %s, %s, %s, %s, %s)",
                          (telegram_id, name, age, sex, interested_in, about_me), verbose=False)
        return jsonify({"message": "User created successfully"}), 201
    else:
        return jsonify({"error": "Missing required fields"}), 400

# Get all users
@app.route("/users", methods=["GET"])
def get_users():
    users = dal.fetch_as_list("SELECT * FROM User", show=False, dictionary=True)
    return jsonify(users)

@app.route("/users/<int:telegram_id>", methods=['GET'])
def get_user_by_id(telegram_id):
    query = f"SELECT * FROM User WHERE telegram_id = {telegram_id};"
    user = dal.fetch_as_list(query, show=False, dictionary=True)
    return jsonify(user)

@app.route("/seek_for_partner/<int:telegram_id>", methods=['GET'])
def get_list_of_partners(telegram_id):
    query = f"SELECT * FROM User WHERE telegram_id = {telegram_id};"
    user = dal.fetch_as_list(query, show=False, dictionary=True)[0]
    age = int(user['Age'])
    sex = user['Sex']
    interest = user['Seek_cluster']

    if interest == 'ManWoman':
        query = f"""
                SELECT telegram_id FROM User WHERE telegram_id != {telegram_id}
                and Age<={age+10} and Age>={age-10} and 
                I_want_to_seek=1 and Seek_cluster='{interest}'
                and Sex != '{sex}'
                 """
    else:
        query = f"""
                SELECT telegram_id FROM User WHERE telegram_id != {telegram_id}
                and Age<={age+15} and Age>={age-15} and 
                I_want_to_seek=1 and Seek_cluster='{interest}'
                 """
    interaction_ids = dal.fetch_as_list(f"select interacted_user_id from interactions where user_id={telegram_id}",
                                         show=False, dictionary=True)
    match_ids = dal.fetch_as_list(f"select matched_user_id from matches where user_id={telegram_id}",
                                         show=False, dictionary=True)
    
    interaction_ids = [i['interacted_user_id'] for i in interaction_ids]
    match_ids = [i['matched_user_id'] for i in match_ids]

    all_ids = match_ids + interaction_ids

    del match_ids, interaction_ids

    users = dal.fetch_as_list(query, show=False, dictionary=True)
    users = [i['telegram_id'] for i in users if i['telegram_id'] not in all_ids]
    shuffle(users)
    users = users[:10] 


    return jsonify(users)

# Get a match
@app.route("/match/<int:user_id>/<int:matched_user_id>", methods=["GET"])
def get_match(user_id, matched_user_id):
    match = dal.fetch_as_list(f"SELECT * FROM matches where user_id={user_id} and matched_user_id={matched_user_id}", 
                                     show=False, dictionary=True)
    return jsonify(match)

# password check
@app.route("/superuser_login/<string:name>/<string:user_hash>/<int:user_id>", methods=["GET"])
def superuser_login(name, user_hash, user_id): 
    user = dal.fetch_as_list(f"SELECT * FROM SuperUser where name='{name}' and password_hash='{user_hash}' and telegram_id={user_id}", 
                                     show=False, dictionary=True)
    if user:
        return make_response("Login succesful", 200)
    else:
        return make_response("Login failed", 404)

@app.route("/most_reported_user", methods=["GET"])
def most_reported_user():
    user = dal.fetch_as_list(f"""SELECT reported_user_id, COUNT(*) AS report_count
                                FROM Reports
                                WHERE status = 'pending'
                                GROUP BY reported_user_id
                                ORDER BY report_count DESC
                                LIMIT 1;
                             """, show=False, dictionary=True)
    
    if user:
        return jsonify(user), 200
    else:
        return jsonify({'message': "not found"}), 404


@app.route("/report_user", methods=["POST"])
def report_user():
    try:
        data = request.json
        reporter_id = data['reporter_id']
        reported_user_id = data['reported_user_id']
        dal.execute_query("INSERT INTO Reports (reporter_id, reported_user_id) VALUES (%s, %s)",
                                (reporter_id, reported_user_id), verbose=False)
        return jsonify({"message": "Report created successfully"}), 201
    except:
        return jsonify({"error": "Error encountered"}), 403


@app.route("/change_user_report_status/<int:user_id>", methods=["PUT"])
def change_user_report_status(user_id):
    data = request.json
    updated_rows = dal.update_data('Reports', [data], [f'reported_user_id = {user_id}'])
    if updated_rows > 0:
        if data['status']=='banned':
            dal.update_data('User', [{'Is_banned': 1}], [f'telegram_id = {user_id}'])
        return jsonify({'message': 'User updated successfully'}), 200
    else:
        return jsonify({'message': 'User not found'}), 404
    
# Create a new interaction
@app.route("/interactions", methods=["POST"])
def create_interaction():
    data = request.json
    user_id = data.get("user_id")
    interacted_user_id = data.get("interacted_user_id")
    interaction_type = data.get("interaction_type")
    if user_id and interacted_user_id and interaction_type:
        # Insert the new interaction into the database
        dal.execute_query("INSERT INTO Interactions (user_id, interacted_user_id, interaction_type) VALUES (%s, %s, %s)",
                          (user_id, interacted_user_id, interaction_type), verbose=False)
        return jsonify({"message": "Interaction created successfully"}), 201
    else:
        return jsonify({"error": "Missing required fields"}), 400

# Get all interactions
@app.route("/interactions", methods=["GET"])
def get_interactions():
    interactions = dal.fetch_as_list("SELECT * FROM Interactions", show=False, dictionary=True)
    return jsonify(interactions)

@app.route("/interactions/<int:user_id>", methods=['GET'])
def get_interactions_by_user_id(user_id):
    query = f"SELECT * FROM Interactions WHERE user_id = {user_id};"
    interactions = dal.fetch_as_list(query, show=False, dictionary=True)
    return jsonify(interactions)

# Function to handle deleting an interaction by ID
@app.route("/interactions_by_time", methods=['DELETE'])
def delete_interactions_by_time():

    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    deleted_rows = dal.delete_data('Interactions', 
                                   f'WHERE TIMESTAMPDIFF(HOUR, interaction_time, {current_datetime})>1')
    if deleted_rows > 0:
        return jsonify({'message': 'Interactions deleted successfully'}), 200
    else:
        return jsonify({'message': 'Interactions not found'}), 404

# Function to handle deleting an interaction by ID
@app.route("/interactions/<int:interaction_id>", methods=['DELETE'])
def delete_interaction(interaction_id):
    deleted_rows = dal.delete_data('Interactions', f'interaction_id = {interaction_id}')
    if deleted_rows > 0:
        return jsonify({'message': 'Interaction deleted successfully'}), 200
    else:
        return jsonify({'message': 'Interaction not found'}), 404

# Function to handle deleting a user
@app.route("/users/<int:telegram_id>", methods=['DELETE'])
def delete_user(telegram_id):
    deleted_rows = dal.delete_data('User', f'telegram_id = {telegram_id}')
    if deleted_rows > 0:
        return jsonify({'message': 'User deleted successfully'}), 200
    else:
        return jsonify({'message': 'User not found'}), 404

# Function to handle updating a user
@app.route("/users/<int:telegram_id>", methods=['PUT'])
def update_user(telegram_id):
    data = request.json
    updated_rows = dal.update_data('User', [data], [f'telegram_id = {telegram_id}'])
    if updated_rows > 0:
        return jsonify({'message': 'User updated successfully'}), 200
    else:
        return jsonify({'message': 'User not found'}), 404

# Function to handle updating an interaction
@app.route("/interactions/<int:interaction_id>", methods=['PUT'])
def update_interaction(interaction_id):
    data = request.json
    updated_rows = dal.update_data('Interactions', [data], [f'interaction_id = {interaction_id}'])
    if updated_rows > 0:
        return jsonify({'message': 'Interaction updated successfully'}), 200
    else:
        return jsonify({'message': 'Interaction not found'}), 404
    

    
if __name__ == "__main__":
    app.run(debug=True)
