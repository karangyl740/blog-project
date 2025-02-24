import json
import base64
import os  # Import the 'os' module
from datetime import timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, UserMixin, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuration
BLOG_FILE = "blog_data.json"

# Use os.path.abspath to create an absolute path to the database file
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///database.db'
app.config["SECRET_KEY"] = "DEVA"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=10)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Corrected: Should be 'login' to match your route


class User(db.Model, UserMixin):
    __tablename__ = "users"  # Corrected: Use __tablename__ instead of _tablename_
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)  # Added nullable=False
    email = db.Column(db.String(100), unique=True, nullable=False)  # Added unique=True and nullable=False
    password_hash = db.Column(db.String(200), nullable=False)  # Added nullable=False
    role = db.Column(db.String(100), default="user")

    def __repr__(self):  # Corrected: Use __repr__ instead of _repr_
        return f"User   ('{self.username}', '{self.email}', '{self.role}')"

    def set_password(self, password):  # renamed save_hash_password to set_password for better readability
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):  # renamed check_hash_password to check_password for better readability
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def home():
    return render_template('home.html')


@app.route("/signup")
def signup():
    return render_template('signup.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            flash("Please fill in all fields")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("User    already exists")
            return redirect(url_for("signup"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("User    registered successfully. Please log in.")
        return redirect(url_for("login"))  # Redirect to login after registration

    return redirect(url_for("signup"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            session.permanent = True
            flash("User    Logged In Successfully")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password")
            return render_template("login.html")  # Render login.html with error

    return render_template("login.html")  # Render login.html initially


@app.route("/logout")
@login_required
def logout():  # added login_required decorator
    logout_user()
    flash("User    Logged out Successfully")
    return redirect(url_for("home"))


def role_required(role):
    def decorator(func):
        @wraps(func)
        def wrap(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash("Unauthorized Access")
                return redirect(url_for("login"))
            return func(*args, **kwargs)

        return wrap

    return decorator


@app.route("/admin")
@login_required
@role_required("admin")
def admin():
    users_data = User.query.filter_by(role="user").all()
    return render_template("admin.html", users=users_data)


@app.route("/deleteUsers/<int:id>") # Added int:id for proper type conversion
@login_required
@role_required("admin")
def deleteUsers(id):
    user_data = User.query.filter_by(id=id).first()
    if user_data: # add check if user exists
        try:
            db.session.delete(user_data)
            db.session.commit()
            return redirect(url_for("admin"))
        except Exception as e:
            flash("Error deleting user: " + str(e))
            return redirect(url_for("admin"))
    else:
        flash("User    not found.")
        return redirect(url_for("admin")) # Or handle the case where the user doesn't exist


# Helper functions
def load_blogs():
    """Load blog posts from JSON file."""
    if os.path.exists(BLOG_FILE):
        try:
            with open(BLOG_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return []  # Return an empty list if JSON is invalid
    return []


def save_blogs(blogs):
    """Save blog posts to JSON file."""
    with open(BLOG_FILE, "w") as file:
        json.dump(blogs, file, indent=4)  # include indent=4


def get_blog(blog_id):
    """Get a blog post by ID."""
    blogs = load_blogs()
    return next((b for b in blogs if b["id"] == int(blog_id)), None)


# Routes
@app.route("/dashboard")
def dashboard():
    """Render the dashboard page."""
    return render_template("dashboard.html")


@app.route("/blog-form")
def blog_form():
    """Render the blog form page."""
    return render_template("user_blog_submit.html")


@app.route("/submit-blog", methods=["POST"])
def submit_blog():
    """Handle blog submission."""
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        title = request.form["title"]
        category = request.form["category"]
        content = request.form["content"]
        image = request.files.get("image")
        date = request.form.get("date")
        

        # Convert image to Base64 if uploaded
        image_base64 = ""
        if image:
            image_base64 = base64.b64encode(image.read()).decode("utf-8")

        blogs = load_blogs()
        new_blog = {
            "id": len(blogs) + 1,
            "name": name,
            "email": email,
            "title": title,
            "category": category,
            "content": content,
            "image": image_base64,
            "date": date
        } # Closing curly brace added here

        try:
            blogs.append(new_blog)
            save_blogs(blogs)
            return redirect(url_for("all_blog_page"))
        except Exception as e:
            flash("Error saving blog: " + str(e))
            return render_template("user_blog_submit.html")

    return render_template("user_blog_submit.html")


@app.route("/story")
def story():
    """Render the story page."""
    return render_template("aboutus.html")


@app.route("/Qt")
def policy():
    """Render the story page."""
    return render_template("medium.html")

@app.route("/all_blogs")
def all_blogs():
    """Render all blog posts."""
    blogs = load_blogs()
    return render_template("all_blog_page.html", posts=blogs)


@app.route("/templatePage")
def templatePage():
    """Render the template page."""
    return render_template("template.html")


@app.route("/blog/<int:blog_id>") # Corrected route definition
def blog_detail(blog_id):
    """Render a blog post detail page."""
    blog = get_blog(blog_id)
    if not blog:
        return "Blog post not found", 404
    return render_template("blog_detail.html", blog=blog)


@app.route("/delete_blog/<int:blog_id>", methods=["POST"]) # Corrected route definition and added methods
def delete_blog(blog_id):
    """Delete a blog post."""
    blogs = load_blogs()
    blog = next((b for b in blogs if b["id"] == int(blog_id)), None)
    if blog: 
        try:
            blogs = [b for b in blogs if b["id"] != int(blog_id)]
            save_blogs(blogs)
            return jsonify({"message": "Blog deleted successfully"}), 200
        except Exception as e:
            return jsonify({"message": "Error deleting blog: " + str(e)}), 500
    else:
        return jsonify({"message": "Blog not found"}), 404


with app.app_context():
    db.create_all()  # moved db.create_all() inside app.app_context()
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", email="admin@gmail.com", role="admin")
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
    
