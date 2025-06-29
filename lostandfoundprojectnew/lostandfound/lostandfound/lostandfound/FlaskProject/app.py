from flask import Flask, render_template, request, redirect, url_for, jsonify, abort, flash, session
import json
import os
import qrcode
from io import BytesIO
import base64
from datetime import datetime
from werkzeug.utils import secure_filename
import sqlite3
from collections import namedtuple

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

USERS_FILE = 'users.json'
DATA_FILE = 'data.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def get_db_connection():
    conn = sqlite3.connect('lost_and_found.db')  
    conn.row_factory = sqlite3.Row  
    return conn


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def generate_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def find_item(item_id):
    data = load_data()
    for item in data:
        if item['id'] == item_id:
            return item
    return None

@app.route('/')
def homescreen():
    return render_template('homescreen.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['full_name']  
        email = request.form['email']
        password = request.form['password']
        users = load_users()
        if email in users:
            return render_template('signup.html', error='User already exists')
        users[email] = {'password': password, 'name': name}
        save_users(users)
        session['user'] = email
        session['name'] = name
        return redirect(url_for('home')) 
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        users = load_users()

    
        if email in users and users[email]['password'] == password:
            session['user'] = email                
            session['name'] = users[email]['name'] 
            return redirect(url_for('home'))       

        
        return render_template('login.html', error='Invalid Credentials')

    return render_template('login.html')

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    items = load_data()
    


    filter_type = request.args.get('type')
    filter_status = request.args.get('status')
    filter_location = request.args.get('location')
    filter_thing = request.args.get('thing')

    if filter_type:
        items = [i for i in items if i['type'].lower() == filter_type.lower()]
    if filter_status:
        items = [i for i in items if i['status'].lower() == filter_status.lower()]
    if filter_location:
        items = [i for i in items if filter_location.lower() in i['location'].lower()]
    if filter_thing:
        items = [i for i in items if filter_thing.lower() in i['description'].lower()]

    filtered_count = len(items)
    unclaimed_items = [i for i in items if i['status'].lower() == 'unclaimed']
    claimed_items = [i for i in items if i['status'].lower() == 'claimed']

    return render_template(
        'home.html',
        unclaimed_items=unclaimed_items,
        claimed_items=claimed_items,
        filtered_count=filtered_count,
        username=session.get('name')  
    )


@app.route('/item/<int:item_id>')
def item_details(item_id):
    
    if 'user' not in session:
        return redirect(url_for('login'))

   
    item = find_item(item_id)
    if not item:
        abort(404)

    
    url = url_for('item_details', item_id=item_id, _external=True)

    
    qr_code_img = generate_qr_code(url)

    
    lat = item.get('latitude', 22.7196)
    lng = item.get('longitude', 75.8577)

    
    user_email = session.get('user', 'Guest')

    return render_template(
        'item_details.html',
        item=item,
        qr_code_img=qr_code_img,
        latitude=lat,
        longitude=lng,
        user=user_email,
        item_id=item_id
    )


@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        data = load_data()
        new_id = max([item['id'] for item in data], default=0) + 1
        item_type = request.form.get('type')
        description = request.form.get('description')
        location = request.form.get('location')
        reporter_name = request.form.get('reporter_name')
        reporter_username = request.form.get('reporter_username')
        reporter_email = request.form.get('reporter_email')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        image_file = request.files.get('image')

        filename = ''
        if image_file and allowed_file(image_file.filename):
            filename = f"{new_id}_{secure_filename(image_file.filename)}"
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_file.save(upload_path)

        new_item = {
            "id": new_id,
            "type": item_type,
            "description": description,
            "location": location,
            "reporter_name": reporter_name,
            "reporter_username": reporter_username,
            "reporter_email": reporter_email,
            "image": f"uploads/{filename}" if filename else '',
            "status": "Unclaimed",
            "messages": [],
            "latitude": float(latitude) if latitude else 22.7196,
            "longitude": float(longitude) if longitude else 75.8577,
        }

        data.append(new_item)
        save_data(data)
        flash("Report submitted successfully!", "success")
        return redirect(url_for('search'))  

    return render_template('lost.html') 

@app.route('/item/<int:item_id>/claim-toggle', methods=['POST'])
def toggle_claim(item_id):
    data = load_data()
    for i, item in enumerate(data):
        if item['id'] == item_id:
            item['status'] = 'Claimed' if item.get('status') == 'Unclaimed' else 'Unclaimed'
            data[i] = item
            save_data(data)
            flash(f"Item marked as {item['status']}.", "success")
            break
    return redirect(url_for('item_details', item_id=item_id))

@app.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(item_id):
    item = find_item(item_id)
    if not item:
        abort(404)
    if request.method == 'POST':
        item['description'] = request.form.get('description')
        item['location'] = request.form.get('location')
        item['reporter_email'] = request.form.get('reporter_email')
        data = load_data()
        for i, it in enumerate(data):
            if it['id'] == item_id:
                data[i] = item
                break
        save_data(data)
        flash("Item updated successfully!", "success")
        return redirect(url_for('item_details', item_id=item_id))
    return render_template('edit_detail.html', item=item)


@app.context_processor
def inject_user():
    return dict(username=session.get('name'))


@app.route('/delete_report/<int:report_id>', methods=['GET', 'POST'])
def delete_report(report_id):
    if request.method == 'POST':
        data = load_data()
        data = [item for item in data if item['id'] != report_id]
        save_data(data)
        flash("Item deleted successfully!", "success")
        return redirect(url_for('search'))
    else:
        item = find_item(report_id)
        if not item:
            abort(404)
        return render_template("delete_report.html", report_id=report_id)

@app.route('/lost')
def lost():
    return render_template('lost.html')
@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/search', methods=['GET'])
def search():
    type_filter = request.args.get('type', '').strip().lower()
    status_filter = request.args.get('status', '').strip().lower()
    location_filter = request.args.get('location', '').strip().lower()
    thing_filter = request.args.get('thing', '').strip().lower()

    with open('data.json', 'r') as f:
        all_items = json.load(f)

    filtered_items = []
        
    for item in all_items:
        if (
            (not type_filter or type_filter in item['type'].lower())
            and (not status_filter or status_filter in item['status'].lower())
            and (not location_filter or location_filter in item['location'].lower())
            and (not thing_filter or thing_filter in item['description'].lower())
        ):
            filtered_items.append(item)

    return render_template(
        'search.html',
        items=filtered_items,
        
        total_results=len(filtered_items)
    )


@app.route('/found')
def found():
    return render_template('found.html')


@app.route('/chat1/')
@app.route('/chat1/<int:report_id>')
def chat1(report_id=None):
    if report_id is None:
        report_id = 1  # default value
    return render_template('chat1.html', report_id=report_id)




@app.route('/chat/<int:item_id>', methods=['GET', 'POST'])
def chat(item_id):
    item = find_item(item_id)
    if not item:
        abort(404)

    if request.method == 'POST':
        sender = request.form.get('sender')
        text = request.form.get('text')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_message = {"sender": sender, "text": text, "timestamp": timestamp}
        item['messages'].append(new_message)

        data = load_data()
        for i, it in enumerate(data):
            if it['id'] == item_id:
                data[i] = item
                break
        save_data(data)

        return redirect(url_for('chat', item_id=item_id))

    return render_template('chat.html', item=item)

@app.route('/logout')
def logout():
    session.clear()
    return render_template('logout.html')


if __name__ == '__main__':
    app.run(debug=True)
