from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session
from flask_migrate import Migrate
from models import db, User, GroceryList, GroceryItem,ListShare
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import os, json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

migrate = Migrate(app, db)  # initialize migrate

firebase_json = os.getenv("FIREBASE_CRED")
cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)

firebase_admin.initialize_app(cred)

# Create DB
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            return "User already exists"
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session.permanent = True 
            session['user_id'] = user.id
            session['username'] = user.username

            return redirect(url_for('dashboard'))
        return "Invalid credentials"
    return render_template('login.html')


@app.route('/sessionLogin', methods=['POST'])
def session_login():
    data = request.get_json()
    id_token = data.get('idToken')

    if not id_token:
        return jsonify({'error': 'Missing ID token'}), 400

    try:
        # Verify Firebase ID token
        decoded_token = firebase_auth.verify_id_token(id_token)
        firebase_uid = decoded_token['uid']
        firebase_email = decoded_token.get('email')

        # Check if user exists by email
        user = User.query.filter_by(email=firebase_email).first()

        # If user doesn't exist, create one with default username
        if not user:
            user = User(email=firebase_email, username=firebase_email.split('@')[0])
            db.session.add(user)
            db.session.commit()

        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print("Error verifying ID token:", str(e))
        return jsonify({'error': 'Invalid ID token'}), 400


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']

    # Lists created by user
    created_lists = GroceryList.query.filter_by(user_id=user_id).all()

    # Lists shared with user
    shared_lists = GroceryList.query \
        .join(ListShare, GroceryList.id == ListShare.list_id) \
        .filter(ListShare.user_id == user_id).all()

    # Combine both
    all_lists = created_lists + shared_lists

    return render_template('dashboard.html', lists=all_lists)


@app.route('/create_list', methods=['GET', 'POST'])
@login_required
def create_list():
    if request.method == 'POST':
        name = request.form['name']
        user = User.query.get(session['user_id'])

        new_list = GroceryList(
            name=name,
            user_id=user.id,
            created_by=user.id  # ✅ This fixes the issue
        )

        db.session.add(new_list)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_list.html')



@app.route('/add_list', methods=['POST'])
@login_required
def add_list():
    name = request.form['list_name']
    new_list = GroceryList(name=name, user_id=session['user_id'])
    db.session.add(new_list)
    db.session.commit()
    return redirect(url_for('dashboard'))




@app.route("/list/<int:list_id>/add", methods=["POST"])
@login_required
def add_item(list_id):
    item_name = request.form.get("name")
    quantity = request.form.get("quantity")
    
    if not item_name or not quantity:
        return redirect(url_for("view_list", list_id=list_id))

    new_item = GroceryItem(
        name=item_name,
        quantity=quantity,
        list_id=list_id,
        user_id=session["user_id"]
    )
    db.session.add(new_item)
    db.session.commit()

    # ✅ Redirect back to the same list page
    return redirect(url_for("view_list", list_id=list_id))


@app.route('/toggle_item/<int:item_id>', methods=["POST"])
@login_required
def toggle_item(item_id):
    item = GroceryItem.query.get_or_404(item_id)
    item.completed = not item.completed
    db.session.commit()
    return jsonify({'success': True, 'completed': item.completed, 'list_id': item.list_id})


@app.route('/delete_item/<int:item_id>', methods=["POST"])
@login_required
def delete_item(item_id):
    item = GroceryItem.query.get_or_404(item_id)
    list_id = item.list_id
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True, 'list_id': list_id})


@app.route('/list/<int:list_id>')
@login_required
def view_list(list_id):
    grocery_list = GroceryList.query.get_or_404(list_id)
    items = GroceryItem.query.filter_by(list_id=list_id).all()
    return render_template('list.html', grocery_list=grocery_list, items=items)

@app.route('/item/<int:item_id>/update', methods=["POST"])
@login_required
def update_item(item_id):
    item = GroceryItem.query.get_or_404(item_id)
    data = request.get_json()
    item.name = data['name']
    item.quantity = data['quantity']
    db.session.commit()
    return jsonify({'success': True})


@app.route('/delete_list/<int:list_id>')
@login_required
def delete_list(list_id):
    grocery_list = GroceryList.query.get(list_id)
    for item in grocery_list.items:
        db.session.delete(item)
    db.session.delete(grocery_list)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/list/<int:list_id>/share', methods=['GET', 'POST'])
@login_required
def share_list(list_id):
    grocery_list = GroceryList.query.get_or_404(list_id)

    # ✅ FIXED: Use user_id instead of created_by
    if grocery_list.user_id != session['user_id']:
        return "Unauthorized", 403

    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()

        if not user:
            flash('User not found', 'danger')
        else:
            already_shared = ListShare.query.filter_by(list_id=list_id, user_id=user.id).first()
            if not already_shared and user.id != session['user_id']:
                new_share = ListShare(list_id=list_id, user_id=user.id)
                db.session.add(new_share)
                db.session.commit()
                flash(f'Shared with {user.username}', 'success')
            else:
                flash('User already has access or is the creator', 'warning')

        return redirect(url_for('share_list', list_id=list_id))

    # Fetch users who have access
    shared_user_ids = [s.user_id for s in ListShare.query.filter_by(list_id=list_id).all()]
    shared_users = User.query.filter(User.id.in_(shared_user_ids)).all()
    
    creator = User.query.get(grocery_list.user_id)  # also fixed here
    members = [creator] + shared_users

    return render_template('share_list.html', list=grocery_list, members=members)


@app.route('/list/<int:list_id>/unshare/<int:user_id>', methods=['GET'])
@login_required
def unshare_list(list_id, user_id):  
    grocery_list = GroceryList.query.get_or_404(list_id)
    # Only the creator can unshare
    if grocery_list.created_by != session['user_id']:
        return "Unauthorized", 403

    # Prevent removing the creator themselves
    if user_id == grocery_list.created_by:
        flash('You cannot remove the creator from the list.', 'danger')
        return redirect(url_for('share_list', list_id=list_id))

    share = ListShare.query.filter_by(list_id=list_id, user_id=user_id).first()
    if share:
        db.session.delete(share)
        db.session.commit()
        flash('User removed from the list', 'success')
    else:
        flash('User not found or not shared', 'warning')

    return redirect(url_for('share_list', list_id=list_id))


if __name__ == '__main__':
    app.run(debug=True)
