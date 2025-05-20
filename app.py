from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime


load_dotenv("supabase.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL or KEY is missing. Check your .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Decorator
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

        # Check if user exists
        response = supabase.table("users").select("*").eq("username", username).execute()
        if response.data:
            return "User already exists"

        supabase.table("users").insert({"username": username, "password": password}).execute()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        response = supabase.table("users").select("*").eq("username", username).execute()
        user = response.data[0] if response.data else None

        if user and check_password_hash(user["password"], password):
            session['user_id'] = user["id"]
            session['username'] = user["username"]
            return redirect(url_for('dashboard'))

        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']

    # Lists owned by user
    owned_lists = supabase.table("grocery_lists").select("*").eq("created_by", user_id).execute().data or []

    # Lists shared with user
    shares_response = supabase.table("list_shares").select("list_id").eq("shared_with", user_id).execute()
    shared_list_ids = [share["list_id"] for share in shares_response.data] if shares_response.data else []

    shared_lists = []
    if shared_list_ids:
        shared_lists = supabase.table("grocery_lists").select("*").in_("id", shared_list_ids).execute().data or []

    # Combine lists and attach items to each
    all_lists = owned_lists + shared_lists
    for lst in all_lists:
        items = supabase.table("grocery_items").select("*").eq("list_id", lst["id"]).execute().data or []
        lst["items"] = items

    # Convert created_at from string to datetime
        if "created_at" in lst and isinstance(lst["created_at"], str):
            lst["created_at"] = datetime.fromisoformat(lst["created_at"].replace("Z", "+00:00"))



    return render_template("dashboard.html", lists=all_lists)


@app.route('/create_list', methods=['GET', 'POST'])
@login_required
def create_list():
    if request.method == 'POST':
        name = request.form['name']
        user_id = session['user_id']

        supabase.table("grocery_lists").insert({
            "name": name,
            "created_by": user_id,
            "user_id": user_id
        }).execute()

        return redirect(url_for('dashboard'))

    return render_template('create_list.html')

@app.route('/add_list', methods=['POST'])
@login_required
def add_list():
    name = request.form['list_name']
    user_id = session['user_id']

    supabase.table("grocery_lists").insert({
        "name": name,
        "created_by": user_id,
        "user_id": user_id
    }).execute()

    return redirect(url_for('dashboard'))

@app.route('/list/<int:list_id>/add', methods=['POST'])
@login_required
def add_item(list_id):
    name = request.form.get("name")
    quantity = request.form.get("quantity")
    user_id = session['user_id']
    username = session['username']

    if name and quantity:
        supabase.table("grocery_items").insert({
            "name": name,
            "quantity": quantity,
            "list_id": list_id,
            "user_id": user_id,
            "added_by": username,  # ✅ This line adds who added the item
            "completed": False
        }).execute()

    return redirect(url_for("view_list", list_id=list_id))

@app.route('/toggle_item/<int:item_id>', methods=['POST'])
@login_required
def toggle_item(item_id):
    item = supabase.table("grocery_items").select("completed", "list_id").eq("id", item_id).execute().data
    if not item:
        return jsonify(success=False), 404

    item = item[0]
    new_status = not item["completed"]
    supabase.table("grocery_items").update({"completed": new_status}).eq("id", item_id).execute()

    return jsonify(success=True, completed=new_status, list_id=item["list_id"])

@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = supabase.table("grocery_items").select("list_id").eq("id", item_id).execute().data
    if not item:
        return jsonify(success=False), 404

    list_id = item[0]["list_id"]
    supabase.table("grocery_items").delete().eq("id", item_id).execute()

    return jsonify(success=True, list_id=list_id)

@app.route('/list/<int:list_id>')
@login_required
def view_list(list_id):
    # Fetch the list
    grocery_list_data = (
        supabase
        .table("grocery_lists")
        .select("*")
        .eq("id", list_id)
        .execute()
        .data
    )
    if not grocery_list_data:
        return "List not found", 404
    grocery_list = grocery_list_data[0]

    # Fetch shared users with their usernames
    shares = (
        supabase
        .table("list_shares")
        .select("shared_with, users(username)")
        .eq("list_id", list_id)
        .execute()
        .data or []
    )

    # Fetch items with user info
    items = (
        supabase
        .table("grocery_items")
        .select("*, users(username)")
        .eq("list_id", list_id)
        .order("added_at", desc=False)
        .execute()
        .data or []
    )

    # Parse timestamps for Jinja
    for item in items:
        if "added_at" in item and isinstance(item["added_at"], str):
            try:
                item["added_at"] = datetime.fromisoformat(item["added_at"].replace("Z", "+00:00"))
            except Exception as e:
                print("Error parsing added_at:", e)

    return render_template("list.html", grocery_list=grocery_list, items=items, shares=shares)


@app.route('/item/<int:item_id>/update', methods=['POST'])
@login_required
def update_item(item_id):
    data = request.get_json()
    name = data.get('name')
    quantity = data.get('quantity')

    supabase.table("grocery_items").update({"name": name, "quantity": quantity}).eq("id", item_id).execute()
    return jsonify(success=True)

@app.route('/delete_list/<int:list_id>')
@login_required
def delete_list(list_id):
    supabase.table("grocery_items").delete().eq("list_id", list_id).execute()
    supabase.table("grocery_lists").delete().eq("id", list_id).execute()
    return redirect(url_for('dashboard'))

@app.route('/list/<int:list_id>/share', methods=['GET', 'POST'])
@login_required
def share_list(list_id):
    grocery_list = supabase.table("grocery_lists").select("*").eq("id", list_id).execute().data
    if not grocery_list:
        return "List not found", 404
    grocery_list = grocery_list[0]

    if grocery_list["created_by"] != session["user_id"]:
        return "Unauthorized", 403

    if request.method == 'POST':
        username = request.form['username']
        user_resp = supabase.table("users").select("*").eq("username", username).execute()
        if not user_resp.data:
            flash('User not found', 'danger')
        else:
            user = user_resp.data[0]
            if user["id"] != session["user_id"]:
                existing_share = supabase.table("list_shares") \
                    .select("*").eq("list_id", list_id).eq("shared_with", user["id"]).execute().data
                if not existing_share:
                    supabase.table("list_shares").insert({
                        "list_id": list_id,
                        "shared_with": user["id"]
                    }).execute()
                    flash(f"List shared with {user['username']}", 'success')
                else:
                    flash("Already shared", "warning")
        return redirect(url_for("share_list", list_id=list_id))

    shares = supabase.table("list_shares").select("shared_with").eq("list_id", list_id).execute().data or []
    shared_user_ids = [s["shared_with"] for s in shares]

    shared_users = supabase.table("users").select("*").in_("id", shared_user_ids).execute().data or []
    creator = supabase.table("users").select("*").eq("id", grocery_list["created_by"]).execute().data[0]

    members = [creator] + shared_users
    return render_template("share_list.html", list=grocery_list, members=members)

@app.route('/list/<int:list_id>/unshare/<int:user_id>')
@login_required
def unshare_list(list_id, user_id):
    grocery_list = supabase.table("grocery_lists").select("*").eq("id", list_id).execute().data
    if not grocery_list:
        return "List not found", 404
    grocery_list = grocery_list[0]

    if grocery_list["created_by"] != session["user_id"]:
        return "Unauthorized", 403

    if user_id == grocery_list["created_by"]:
        flash("Cannot remove the creator.", "danger")
    else:
        supabase.table("list_shares").delete().eq("list_id", list_id).eq("shared_with", user_id).execute()
        flash("User removed.", "success")

    return redirect(url_for("share_list", list_id=list_id))

if __name__ == '__main__':
    app.run(debug=True)
